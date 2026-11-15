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
sync_site.py -- 把 site/ 的落地页同步到仓库根目录。

为什么需要:
  EdgeOne Pages 的「输出目录」如果填的是根目录, 就找不到 site/ 下的文件;
  如果填 site/, 又可能因为某些配置只部署部分文件。
  两个位置都放一份, 就无论输出目录怎么填都能拿到完整站点。

用法:
    python tools/sync_site.py          # 同步
    python tools/sync_site.py --check  # 只检查是否一致
"""

import argparse
import filecmp
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAIRS = [("site/index.html", "index.html"), ("site/config.json", "config.json")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查不复制")
    args = ap.parse_args()

    print("同步根目录副本:")
    changed = 0
    for src_rel, dst_rel in PAIRS:
        src = os.path.join(ROOT, src_rel.replace("/", os.sep))
        dst = os.path.join(ROOT, dst_rel.replace("/", os.sep))
        if not os.path.isfile(src):
            print(f"  [SKIP] {src_rel} 不存在")
            continue
        if os.path.isfile(dst) and filecmp.cmp(src, dst, shallow=False):
            print(f"  [OK]   {dst_rel} 已一致")
            continue
        if args.check:
            print(f"  [DIFF] {dst_rel} 与 {src_rel} 不一致")
            changed += 1
            continue
        shutil.copy2(src, dst)
        print(f"  [COPY] {src_rel} -> {dst_rel}")
        changed += 1

    print()
    if changed == 0:
        print("根目录副本已是最新")
    elif args.check:
        print(f"{changed} 个文件需要同步 (跑 python tools/sync_site.py)")
        return 1
    else:
        print(f"已同步 {changed} 个文件, 现在可以 python tools/api_push.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())