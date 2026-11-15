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
api_push.py -- 用 GitHub REST API 提交, 绕开被阻断的 github.com git 端点。

背景:
  某些网络(尤其国内直连 + 某些代理规则)会阻断 github.com:443,
  但 api.github.com 走的是另一条 CDN 路径, 通常仍然通。
  此时 git push 会失败, 但 REST API 可以正常提交。

用法:
    python tools/api_push.py                 # 提交全部改动并推送
    python tools/api_push.py --dry-run       # 只看会提交什么
    python tools/api_push.py --repo user/name

凭据来源(按顺序):
  1. 环境变量 GITHUB_TOKEN / GH_TOKEN
  2. ~/.git-credentials 里的 github.com 条目
  3. gh auth token (如果装了 GitHub CLI)
"""

import argparse
import base64
import json
import os
import re
import subprocess
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GREEN, RED, YELLOW, DIM, RESET = '\033[32m', '\033[31m', '\033[33m', '\033[2m', '\033[0m'
if os.name == 'nt' and not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ''


def ok(msg):    print(f'{GREEN}[OK]{RESET}   {msg}')
def bad(msg):   print(f'{RED}[FAIL]{RESET} {msg}')
def warn(msg):  print(f'{YELLOW}[WARN]{RESET} {msg}')
def info(msg):  print(f'{DIM}[..]{RESET}   {msg}')


def get_token():
    for k in ('GITHUB_TOKEN', 'GH_TOKEN'):
        v = os.environ.get(k)
        if v:
            return v.strip(), 'env ' + k
    cf = os.path.expanduser('~/.git-credentials')
    if os.path.isfile(cf):
        m = re.search(r'https://([^:@/]+):([^@]+)@github\.com',
                      open(cf, encoding='utf-8').read())
        if m:
            return m.group(2), '~/.git-credentials'
    try:
        r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip(), 'gh auth token'
    except Exception:
        pass
    return None, None


class GitHub:
    def __init__(self, token, repo):
        self.token = token
        self.repo = repo
        self.base = 'https://api.github.com/repos/' + repo
        self.h = {
            'Authorization': 'Bearer ' + token,
            'User-Agent': 'nfc-player-api-push',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        }

    def call(self, path, method='GET', body=None, tries=4):
        data = json.dumps(body).encode() if body is not None else None
        last = None
        for i in range(tries):
            try:
                req = urllib.request.Request(self.base + path, data=data,
                                           method=method, headers=self.h)
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                    return r.status, (json.loads(raw) if raw else None)
            except urllib.error.HTTPError as e:
                return e.code, e.read()[:400]
            except Exception as e:
                last = e
                if i < tries - 1:
                    time.sleep(4 * (i + 1))
        raise last


def collect_files():
    # 收集要提交的文件
    files = {}
    for sub in ('site', 'tools', 'audio', 'docs', '.github'):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x not in ('__pycache__', '.git')]
            for f in fn:
                fp = os.path.join(dp, f)
                rel = os.path.relpath(fp, ROOT).replace(os.sep, '/')
                if rel.endswith(('.pyc', '.ndef')):
                    continue
                if rel.startswith('site/') and rel.endswith('.wav'):
                    continue
                files[rel] = open(fp, 'rb').read()
    for f in ('README.md', 'vercel.json', '.gitignore', '.gitattributes',
              'index.html', 'config.json'):
        fp = os.path.join(ROOT, f)
        if os.path.isfile(fp):
            files[f] = open(fp, 'rb').read()
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='burningleaves/nfc-player')
    ap.add_argument('--message', default='chore: 通过 API 更新站点与工具')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    print('=' * 68)
    print('GitHub API 推送 (绕开 github.com git 端点)')
    print('=' * 68)

    tok, src = get_token()
    if not tok:
        bad('找不到 GitHub 凭据')
        info('请设置 GITHUB_TOKEN 环境变量, 或在 ~/.git-credentials 里存一条 github.com 记录')
        return 1
    ok('凭据来源: ' + str(src))

    gh = GitHub(tok, args.repo)

    st, ref = gh.call('/git/ref/heads/main')
    if st != 200:
        bad('拿不到 main 分支 (HTTP ' + str(st) + '): ' + str(ref))
        return 1
    base_sha = ref['object']['sha']
    ok('远程 main = ' + base_sha[:8])

    st, tree = gh.call('/git/trees/' + base_sha + '?recursive=1')
    if st != 200:
        bad('拿不到文件树 (HTTP ' + str(st) + ')')
        return 1
    remote = {t['path']: t for t in tree['tree'] if t['type'] == 'blob'}

    local = collect_files()
    changed = {}
    for path, data in local.items():
        if path not in remote:
            changed[path] = data
            continue
        st, blob = gh.call('/git/blobs/' + remote[path]['sha'])
        if st != 200:
            continue
        remote_bytes = base64.b64decode(blob['content'])
        # 行尾归一化后比较: Git 仓库里是 LF, 本地 Windows 可能是 CRLF
        if remote_bytes.replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n'):
            continue
        changed[path] = data

    print()
    if not changed:
        ok('本地与远程内容一致, 没有需要推送的改动')
        return 0
    info('要推送 ' + str(len(changed)) + ' 个文件:')
    for p in sorted(changed):
        print('   ' + p)

    if args.dry_run:
        print()
        info('--dry-run, 未推送')
        return 0

    entries = []
    for path, data in changed.items():
        st, blob = gh.call('/git/blobs', 'POST', {
            'content': base64.b64encode(data).decode(),
            'encoding': 'base64',
        })
        if st != 201:
            bad('创建 blob 失败 ' + path + ': ' + str(blob))
            return 1
        entries.append({
            'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha'],
        })
    ok(str(len(entries)) + ' 个 blob 已创建')

    st, newtree = gh.call('/git/trees', 'POST', {
        'base_tree': base_sha, 'tree': entries,
    })
    if st != 201:
        bad('创建 tree 失败: ' + str(newtree))
        return 1

    st, commit = gh.call('/git/commits', 'POST', {
        'message': args.message, 'tree': newtree['sha'], 'parents': [base_sha],
    })
    if st != 201:
        bad('创建 commit 失败: ' + str(commit))
        return 1
    ok('commit ' + commit['sha'][:8] + ' 已创建')

    st, upd = gh.call('/git/refs/heads/main', 'PATCH', {'sha': commit['sha']})
    if st not in (200, 204):
        bad('更新分支失败: ' + str(upd))
        return 1

    ok('推送完成 -> ' + args.repo)
    print()
    info('GitHub Actions 会自动重新部署 (约 1~2 分钟)')
    return 0


if __name__ == '__main__':
    sys.exit(main())