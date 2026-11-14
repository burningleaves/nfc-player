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
deploy_check.py -- 部署前自检 + 生成上线所需的一切。

自检项:
  1. site/index.html 存在且含 config.json 解析逻辑
  2. site/config.json 存在且 JSON 合法
  3. 每个音频直链可访问 + 支持 Range (206) + 实测延迟
  4. 打印标签要写入的短 URL 与 NDEF 长度

用法:
    python deploy_check.py --site https://your-domain.com
    python deploy_check.py --site https://your-domain.com --no-net
"""

import argparse
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if os.name == "nt" and not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""


def ok(msg):    print(f"{GREEN}[OK]{RESET}   {msg}")
def bad(msg):   print(f"{RED}[FAIL]{RESET} {msg}")
def warn(msg):  print(f"{YELLOW}[WARN]{RESET} {msg}")
def info(msg):  print(f"{DIM}[..]{RESET}   {msg}")


def check_range(url, timeout=12):
    """返回 (可访问, 支持Range, 状态码, 内容类型, 大小, 毫秒延迟)"""
    t0 = time.time()
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            ms = int((time.time() - t0) * 1000)
            return (True, bool(hdrs.get("content-range")), r.status,
                    hdrs.get("content-type", ""), hdrs.get("content-length", ""), ms)
    except urllib.error.HTTPError as e:
        ms = int((time.time() - t0) * 1000)
        return (False, False, e.code, "", "", ms)
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return (False, False, None, str(e)[:80], "", ms)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="落地页地址")
    ap.add_argument("--no-net", action="store_true", help="跳过网络检查")
    args = ap.parse_args()

    site = args.site.rstrip("/")
    failures = 0

    print("=" * 68)
    print("NFC 碰一碰播歌 · 部署自检")
    print("=" * 68)

    # 1) index.html
    idx = os.path.join(SITE, "index.html")
    if os.path.isfile(idx):
        html = io.open(idx, encoding="utf-8").read()
        ok(f"site/index.html 存在 ({len(html)} 字节)")
        if "resolve(" in html and "config.json" in html:
            ok("落地页含 config.json 解析逻辑")
        else:
            bad("落地页缺少 config.json 解析逻辑")
            failures += 1
    else:
        bad("site/index.html 不存在")
        failures += 1

    # 2) config.json
    cfgp = os.path.join(SITE, "config.json")
    if not os.path.isfile(cfgp):
        bad("site/config.json 不存在 —— 先跑 make_config.py")
        return 1
    try:
        cfg = json.load(io.open(cfgp, encoding="utf-8"))
        ok(f"site/config.json 合法 ({len(cfg.get('songs', []))} 首)")
    except Exception as e:
        bad(f"site/config.json 解析失败: {e}")
        return 1

    songs = cfg.get("songs", [])
    if not songs:
        bad("config.json 里没有歌曲")
        failures += 1

    # 3) 音频直链
    print()
    print("─" * 68)
    print("音频直链检查 (可访问 / Range / 延迟)")
    print("─" * 68)
    for s in songs:
        title = s.get("title", "?")
        urls = [u.strip() for u in s.get("url", "").split("|") if u.strip()]
        if not urls:
            bad(f"[{title}] 没有 url")
            failures += 1
            continue
        if args.no_net:
            info(f"[{title}] 跳过网络检查 (--no-net)")
            continue
        good = 0
        for url in urls:
            if not url.startswith("https://"):
                bad(f"[{title}] 不是 https 直链: {url}")
                failures += 1
                continue
            reachable, has_range, status, ctype, size, ms = check_range(url)
            parts = url.split("/")
            short = parts[2] + "/…" + parts[-1][:30]
            if not reachable:
                bad(f"[{title}] 不可访问 (HTTP {status}, {ms}ms): {short}")
                continue
            if not has_range:
                warn(f"[{title}] 可访问但不支持 Range -> 无法拖进度 ({ms}ms): {short}")
                continue
            if ctype and "text/html" in ctype:
                bad(f"[{title}] 返回 HTML(多半跳到登录页/404页), 不是音频: {short}")
                continue
            good += 1
            slow = "   <-- 慢!" if ms > 3000 else ""
            ok(f"[{title}] OK  206/Range  {ms}ms  {ctype}  {short}{slow}")
        if good == 0:
            bad(f"[{title}] 所有源都不可用")
            failures += 1
        elif good < len(urls):
            warn(f"[{title}] {good}/{len(urls)} 个源可用 (已配回退, 不影响播放)")

    # 4) 标签 URL
    print()
    print("─" * 68)
    print("写进 NFC 标签的 URL")
    print("─" * 68)
    sys.path.insert(0, HERE)
    from nfc_write import encode_ndef_uri

    for s in songs:
        short_url = f"{site}/?id={s.get('id')}"
        data = encode_ndef_uri(short_url)
        fits = len(data) <= 144
        flag = "OK" if fits else "超出 NTAG213(144B), 需 NTAG215+"
        print(f"  [{s.get('title')}]")
        print(f"    {short_url}")
        print(f"    NDEF {len(data)} 字节  {flag}")
        if not fits:
            failures += 1
    if songs:
        print()
        print("写入标签:")
        print(f'  python nfc_write.py "{site}/?id={songs[0].get("id")}"')

    print()
    print("=" * 68)
    if failures:
        print(f"{RED}自检未通过: {failures} 项问题{RESET}")
        return 1
    print(f"{GREEN}自检全部通过{RESET}")
    print("=" * 68)
    print()
    print("下一步: 把 site/ 里的 index.html + config.json 推上去, 托管平台会自动部署。")
    return 0


if __name__ == "__main__":
    sys.exit(main())