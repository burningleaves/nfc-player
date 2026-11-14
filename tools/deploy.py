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
deploy.py -- 一键部署落地页。

支持三种方式, 按顺序自动尝试:

  1. git push     —— 托管平台绑了 GitHub 仓库时, push 即自动部署 (推荐)
  2. edgeone     —— EdgeOne Pages CLI 直接上传 site/ 目录
  3. vercel      —— Vercel CLI 直接上传 site/ 目录

用法:
    python tools/deploy.py                 # 自动选方式
    python tools/deploy.py --method git    # 只走 git push
    python tools/deploy.py --method edgeone
    python tools/deploy.py --method vercel
    python tools/deploy.py --dry-run        # 只检查不执行
"""

import argparse
import os
import shutil
import subprocess

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


def run(cmd, cwd=None, check=False):
    info("$ " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True,
                           capture_output=True, timeout=600)
    except FileNotFoundError:
        bad(f"命令不存在: {cmd[0]}")
        return 127, ""
    except subprocess.TimeoutExpired:
        bad(f"命令超时(10分钟): {cmd[0]}")
        return 124, ""
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        bad(f"退出码 {p.returncode}")
        for line in out.strip().split("\n")[-12:]:
            print('     ' + line)
    return p.returncode, out


def have(cmd):
    return shutil.which(cmd) is not None


def check_site():
    need = ["index.html", "config.json"]
    missing = [f for f in need if not os.path.isfile(os.path.join(SITE, f))]
    if missing:
        bad("site/ 缺少: " + ", ".join(missing))
        return False
    ok("site/ 就绪 (" + ", ".join(need) + ")")
    return True


def deploy_git(dry=False):
    info("方式 1/3: git push (托管平台绑 GitHub 仓库时自动部署)")
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        bad("不是 git 仓库")
        return False
    rc, out = run(["git", "status", "--short"], cwd=ROOT)
    if out.strip():
        warn("有未提交的改动, 先提交:")
        for line in out.strip().split('\n')[:10]:
            print('     ' + line)
    if dry:
        return True
    rc, _ = run(["git", "add", "-A"], cwd=ROOT)
    if rc != 0:
        return False
    rc, out = run(["git", "commit", "-m", "deploy: update site"], cwd=ROOT)
    if rc != 0 and "nothing to commit" not in out.lower():
        return False
    rc, out = run(["git", "push"], cwd=ROOT)
    if rc != 0:
        bad("push 失败 —— 检查 remote 和凭据")
        return False
    ok("已 push, 托管平台会自动重新部署 (通常 1~2 分钟)")
    return True


def deploy_edgeone(dry=False):
    info("方式 2/3: EdgeOne Pages CLI")
    if not have("edgeone"):
        warn("未安装 edgeone CLI —— npm i -g edgeone")
        return False
    if dry:
        ok("edgeone CLI 可用")
        return True
    rc, _ = run(["edgeone", "pages", "deploy", SITE], cwd=ROOT)
    if rc != 0:
        bad("edgeone 部署失败")
        return False
    ok("已通过 EdgeOne 部署")
    return True


def deploy_vercel(dry=False):
    info("方式 3/3: Vercel CLI")
    if not have("vercel"):
        warn("未安装 vercel CLI —— npm i -g vercel")
        return False
    if dry:
        ok("vercel CLI 可用")
        return True
    rc, _ = run(["vercel", "--prod", "--yes", SITE], cwd=ROOT)
    if rc != 0:
        bad("vercel 部署失败")
        return False
    ok("已通过 Vercel 部署")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["auto", "git", "edgeone", "vercel"],
                    default="auto")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("=" * 68)
    print("NFC 碰一碰播歌 · 部署")
    print("=" * 68)
    print()
    if not check_site():
        return 1

    methods = {
        "git": deploy_git,
        "edgeone": deploy_edgeone,
        "vercel": deploy_vercel,
    }

    if args.method == "auto":
        order = ["git", "edgeone", "vercel"]
    else:
        order = [args.method]

    for name in order:
        if methods[name](args.dry_run):
            print()
            ok("部署流程完成")
            return 0
        print()

    bad("所有部署方式都失败了, 请看上面的提示")
    return 1


if __name__ == "__main__":
    sys.exit(main())