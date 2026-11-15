#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io

# Windows 控制台默认 GBK, 强制 UTF-8 输出避免中文乱码
for _s in ('stdout', 'stderr'):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, 'reconfigure'):
        try:
            _f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

"""
cos_upload.py -- 上传文件到腾讯云 COS 并可选开启静态网站托管。

零第三方依赖, 只用标准库实现 COS V5 签名 (TC3-HMAC-SHA256)。

用法:
    # 上传整个 site/ 和 audio/ 并开启静态网站
    python tools/cos_upload.py --secret-id AKID --secret-key SK --bucket mybucket-1250000000

    # 只上传, 不改配置
    python tools/cos_upload.py --secret-id AKID --secret-key SK --bucket mybucket-1250000000 --no-website

    # 从环境变量读密钥 (更安全)
    set TENCENT_SECRET_ID=AKID
    set TENCENT_SECRET_KEY=SK
    python tools/cos_upload.py --bucket mybucket-1250000000

注意:
  - 存储桶必须已创建, 且与密钥同账号同地域
  - 2024年后新建的桶, 默认域名访问 HTML 会变成下载 (Content-Disposition: attachment),
    所以落地页建议放 EdgeOne/Vercel, COS 放音频
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if os.name == 'nt' and not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""


def ok(msg):    print(f"{GREEN}[OK]{RESET}   {msg}")
def bad(msg):   print(f"{RED}[FAIL]{RESET} {msg}")
def warn(msg):  print(f"{YELLOW}[WARN]{RESET} {msg}")
def info(msg):  print(f"{DIM}[..]{RESET}   {msg}")


# ---------- COS V5 签名 ----------

ALGO = "TC3-HMAC-SHA256"
SERVICE = "cos"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


class CosClient:
    def __init__(self, secret_id, secret_key, region, bucket):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        self.bucket = bucket
        self.host = f"{bucket}.cos.{region}.myqcloud.com"

    def _sign_key(self, date):
        """派生签名密钥链"""
        secret_date = hmac_sha256(("TC3" + self.secret_key).encode(), date)
        secret_service = hmac_sha256(secret_date, SERVICE)
        secret_signing = hmac_sha256(secret_service, "tc3_request")
        return secret_signing

    def _sign(self, method, path, query, headers, payload):
        """生成 Authorization 头"""
        t = time.gmtime()
        ts = time.strftime("%Y%m%dT%H%M%SZ", t)
        date = time.strftime("%Y-%m-%d", t)

        # 1. 规范化请求
        canonical_headers = "".join(f"{k.lower()}:{v.strip()}\n" for k, v in sorted(headers.items()))
        signed_headers = ";".join(sorted(k.lower() for k in headers))
        canonical_uri = urllib.parse.quote(path, safe="/-_.~")
        canonical_qs = "&".join(f"{urllib.parse.quote(k, safe="-_.~")}={urllib.parse.quote(str(v), safe="-_.~")}"
                               for k, v in sorted(query.items()))
        canonical_request = "\n".join([method, canonical_uri, canonical_qs,
                                       canonical_headers, signed_headers, sha256(payload)])

        # 2. 待签字符串
        credential_scope = f"{date}/{SERVICE}/tc3_request"
        string_to_sign = "\n".join([ALGO, ts, credential_scope, sha256(canonical_request.encode())])

        # 3. 签名
        signature = hmac.new(self._sign_key(date), string_to_sign.encode(), hashlib.sha256).hexdigest()
        auth = f"{ALGO} Credential={self.secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        return auth, ts

    def request(self, method, path, query=None, body=b"", extra_headers=None, content_type=None):
        query = query or {}
        host = self.host
        headers = {
            "Host": host,
        }
        if content_type:
            headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(body))
        if extra_headers:
            headers.update(extra_headers)

        auth, ts = self._sign(method, path, query, headers, body)
        headers["Authorization"] = auth
        headers["x-cos-date"] = ts

        url = f"https://{host}" + urllib.parse.quote(path, safe="/-_.~")
        if query:
            url += "?" + "&".join(f"{urllib.parse.quote(k, safe="-_.~")}={urllib.parse.quote(str(v), safe="-_.~")}"
                                  for k, v in sorted(query.items()))
        req = urllib.request.Request(url, data=body if body else None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def put_object(self, key, path_on_disk, content_type=None):
        with open(path_on_disk, "rb") as f:
            data = f.read()
        return self.request("PUT", "/" + key, body=data, content_type=content_type)

    def head_object(self, key):
        return self.request("HEAD", "/" + key)

    def get_bucket(self):
        return self.request("GET", "/")

    def put_website(self, index="index.html", error="404.html"):
        body = (
            "<WebsiteConfiguration>"
            f"<IndexDocument><Suffix>{index}</Suffix></IndexDocument>"
            f"<ErrorDocument><Key>{error}</Key></ErrorDocument>"
            "</WebsiteConfiguration>"
        ).encode("utf-8")
        return self.request("PUT", "/?website", body=body, content_type="application/xml")


def guess_type(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".aac": "audio/aac",
        ".js": "application/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }.get(ext, "application/octet-stream")

def main() -> int:
    ap = argparse.ArgumentParser(description="上传到腾讯云 COS")
    ap.add_argument("--secret-id", default=os.environ.get("TENCENT_SECRET_ID", ""))
    ap.add_argument("--secret-key", default=os.environ.get("TENCENT_SECRET_KEY", ""))
    ap.add_argument("--bucket", required=True, help="存储桶名, 含 APPID, 如 mybucket-1250000000")
    ap.add_argument("--region", default="ap-shanghai")
    ap.add_argument("--prefix", default="", help="对象前缀, 如 nfc")
    ap.add_argument("--no-website", action="store_true", help="不开静态网站托管")
    ap.add_argument("--only", default="", help="只上传某个子目录, 如 audio 或 site")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("=" * 68)
    print("腾讯云 COS 上传")
    print("=" * 68)

    if not args.secret_id or not args.secret_key:
        bad("缺少密钥")
        info("用 --secret-id/--secret-key 传, 或设环境变量 TENCENT_SECRET_ID / TENCENT_SECRET_KEY")
        return 1

    c = CosClient(args.secret_id, args.secret_key, args.region, args.bucket)
    ok(f"存储桶: {c.host}")

    # 先验证密钥有效
    st, h, body = c.get_bucket()
    if st == 200:
        ok("密钥验证通过")
    elif st == 403:
        bad(f"密钥无权限 (403): {body[:200]}")
        return 1
    else:
        bad(f"无法访问存储桶 (HTTP {st}): {body[:200]}")
        return 1

    # 收集要上传的文件
    plan = []
    for sub in ("site", "audio"):
        if args.only and args.only != sub:
            continue
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in ("__pycache__", ".git")]
            for f in fn:
                fp = os.path.join(dp, f)
                rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
                key = (args.prefix + "/" + rel) if args.prefix else rel
                plan.append((key, fp))

    if not plan:
        bad("没有找到要上传的文件")
        return 1

    print()
    info(f"要上传 {len(plan)} 个文件:")
    for key, fp in plan:
        print(f"   {key}  ({os.path.getsize(fp)} bytes)")

    if args.dry_run:
        info("--dry-run, 未上传")
        return 0

    # 上传
    failed = 0
    for key, fp in plan:
        st, h, body = c.put_object(key, fp, guess_type(fp))
        if st in (200, 204):
            ok(f"上传 {key}")
        else:
            bad(f"上传失败 {key} (HTTP {st}): {body[:150]}")
            failed += 1

    if failed:
        print()
        bad(f"{failed} 个文件上传失败")
        return 1

    # 开启静态网站托管
    if not args.no_website:
        st, h, body = c.put_website()
        if st in (200, 204):
            ok("静态网站托管已开启 (index.html)")
        else:
            warn(f"开启静态网站失败 (HTTP {st}): {body[:150]}")
            info("这不影响音频直链, 可以忽略")

    print()
    print("=" * 68)
    ok("上传完成")
    print("=" * 68)
    print()
    base = f"https://{c.host}"
    if args.prefix:
        base += "/" + args.prefix
    print("直链:")
    for key, fp in plan:
        print(f"  {base}/{key}")
    print()
    print("⚠️ 2024年后新建的桶, 默认域名访问 HTML 会被强制下载 (Content-Disposition: attachment)"),
    print("   所以落地页建议仍用 EdgeOne, COS 只放音频。")
    return 0


if __name__ == "__main__":
    sys.exit(main())