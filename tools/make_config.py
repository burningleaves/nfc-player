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
#!/usr/bin/env python3
"""
make_config.py -- 生成 site/config.json 与标签用的短 URL。

设计要点:
  NFC 标签只有 144 字节(NTAG213)。如果把音频直链直接塞进标签,
  URL 一长就写不下或写进去很丑。所以:
      标签  ->  https://<user>.github.io/<repo>/p/<短ID>      (极短)
      配置  ->  site/config.json  里按短ID 映射到真实音频直链
  落地页先读 config.json, 再决定播哪一首。

用法:
    python make_config.py --site https://user.github.io/nfc-player \
        --song "我的歌=https://github.com/user/repo/releases/download/v1/song.mp3" \
        --song "另一首=https://github.com/user/repo/releases/download/v1/song2.mp3" \
        --short mysong --short other
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "site")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 NFC 播放配置")
    ap.add_argument("--site", required=True,
                    help="落地页地址, 例如 https://user.github.io/nfc-player")
    ap.add_argument("--song", action="append", default=[],
                    metavar="标题=直链", help="可重复")
    ap.add_argument("--short", action="append", default=[],
                    metavar="短ID", help="可重复, 与 --song 按顺序对应")
    ap.add_argument("--out", default=os.path.join(SITE, "config.json"))
    args = ap.parse_args()

    songs = []
    for i, item in enumerate(args.song):
        if "=" not in item:
            print(f"ERROR: --song 格式应为 标题=直链, 得到: {item}", file=sys.stderr)
            return 2
        title, url = item.split("=", 1)
        title, url = title.strip(), url.strip()
        short = args.short[i] if i < len(args.short) else ""
        if not short:
            # 自动生成短 ID: 标题去掉非字母数字 + 截断
            short = "".join(c for c in title if c.isalnum()).lower()[:12] or f"song{i + 1}"
        songs.append({"id": short, "title": title, "url": url})

    if not songs:
        print("ERROR: 至少要有一首 --song", file=sys.stderr)
        return 2

    # 校验直链形态
    for s in songs:
        urls = [u.strip() for u in s["url"].split("|") if u.strip()]
        for u in urls:
            if not u.startswith("https://"):
                print(f"WARN: [{s['title']}] 直链不是 https, 浏览器可能拦截: {u}",
                      file=sys.stderr)
            if "/releases/download/" in u:
                print(f"WARN: [{s['title']}] Release 资产会 302 跳到 "
                      f"objects.githubusercontent.com, 国内实测 25s 超时 -> 建议改用 "
                      f"raw.githubusercontent.com", file=sys.stderr)
        if len(urls) > 1:
            print(f"INFO: [{s['title']}] {len(urls)} 个回退源, 前一个失败会自动换下一个",
                  file=sys.stderr)

    site = args.site.rstrip("/")
    cfg = {"site": site, "songs": songs}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("=" * 68)
    print("已写出:", os.path.abspath(args.out))
    print("=" * 68)
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    print()
    print("─" * 68)
    print("要写进 NFC 标签的短 URL (每行一个, 一张标签一行):")
    print("─" * 68)
    for s in songs:
        short_url = f"{site}/?id={s['id']}"
        print(f"  {s['title']}")
        print(f"    {short_url}")
        print(f"    (标签内 NDEF 约 {len(short_url) + 2} 字节)")
    print()
    print("写标签: python nfc_write.py \"<上面的短 URL>\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
