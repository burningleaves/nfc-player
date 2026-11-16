#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io

for _s in ("stdout", "stderr"):
    _f = getattr(sys, _s, None)
    if _f is not None and hasattr(_f, "reconfigure"):
        try:
            _f.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

"""
cleanup_remote.py -- 删掉远程仓库里本地已不存在的文件。

api_push.py 是增量推送(只加/改, 不删), 所以本地删掉的文件会留在远程。
这个脚本重建完整 tree, 把远程多出来的文件移除。

用法:
    python tools/cleanup_remote.py site/t.m4a site/_probe.html
    python tools/cleanup_remote.py --all      # 以本地为准全量对齐
"""

import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from api_push import get_token

REPO = "/repos/burningleaves/nfc-player"


def api(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {
        "Authorization": "Bearer " + TOK,
        "User-Agent": "nfc-player-cleanup",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request("https://api.github.com" + path, data=data, method=method, headers=h)
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            return e.code, e.read()[:300]
        except Exception:
            if i == 2:
                raise
            time.sleep(4)


def main():
    global TOK
    cred = get_token()
    if not cred:
        print("找不到 GitHub 凭据")
        return 1
    TOK = cred[0]

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv:
        # 以本地为准: 收集本地所有应存在的文件
        from api_push import collect_files
        local = set(collect_files().keys())
        st, ref = api(REPO + "/git/ref/heads/main")
        base = ref["object"]["sha"]
        st, c = api(REPO + "/git/commits/" + base)
        st, tree = api(REPO + "/git/trees/" + c["tree"]["sha"] + "?recursive=1")
        exclude = set(t["path"] for t in tree["tree"] if t["path"] not in local)
    else:
        exclude = set(args)

    if not exclude:
        print("没有指定要删除的文件")
        return 0

    st, ref = api(REPO + "/git/ref/heads/main")
    base = ref["object"]["sha"]
    st, c = api(REPO + "/git/commits/" + base)
    tree_sha = c["tree"]["sha"]
    st, tree = api(REPO + "/git/trees/" + tree_sha + "?recursive=1")

    entries = []
    removed = []
    for t in tree["tree"]:
        if t["type"] == "tree":
            continue
        if t["path"] in exclude:
            removed.append(t["path"])
            continue
        entries.append({"path": t["path"], "mode": t["mode"], "type": "blob", "sha": t["sha"]})

    if not removed:
        print("远程没有这些文件, 无需清理")
        return 0

    for p in removed:
        print("  [DEL]", p)

    st, newtree = api(REPO + "/git/trees", "POST", {"tree": entries})
    if st != 201:
        print("创建 tree 失败:", newtree)
        return 1

    st, commit = api(REPO + "/git/commits", "POST", {
        "message": "chore: 清理多余文件 " + ", ".join(removed),
        "tree": newtree["sha"],
        "parents": [base],
    })
    if st != 201:
        print("创建 commit 失败:", commit)
        return 1

    st, upd = api(REPO + "/git/refs/heads/main", "PATCH", {"sha": commit["sha"]})
    if st not in (200, 204):
        print("更新分支失败:", upd)
        return 1

    print("已清理, commit", commit["sha"][:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())