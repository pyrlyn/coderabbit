#!/usr/bin/env python3
"""Sync the central .coderabbit.yaml into every non-archived pyrlyn repository.

For each repository: own .coderabbit.yaml that differs from central, and stray variants
(.coderabbit.yml, .github/.coderabbit.yaml, .github/.coderabbit.yml), are deleted by a direct
commit to the default branch. If a ruleset blocks that, the deletion goes into the sync PR
(no bypass). The central file is then added via PR chore/sync-coderabbit-config with squash
auto-merge. Identical repos are skipped.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ORG = os.environ.get("ORG", "pyrlyn")
SELF = os.environ.get("GITHUB_REPOSITORY", f"{ORG}/coderabbit").split("/")[1]
TOKEN = os.environ["GH_TOKEN"]
# Repositories the sync must never touch.
EXCLUDE = {"rtok-net"}
BRANCH = "chore/sync-coderabbit-config"
TARGET = ".coderabbit.yaml"
STRAY = [".coderabbit.yml", ".github/.coderabbit.yaml", ".github/.coderabbit.yml"]
TITLE = "chore: sync central CodeRabbit config"
BODY = f"Synced automatically from {ORG}/{SELF} (scripts/sync.py). Do not edit `{TARGET}` here."


def api(method, path, body=None, ok404=False):
    req = urllib.request.Request(
        f"https://api.github.com{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        if ok404 and e.code == 404:
            return None
        raise RuntimeError(f"{method} {path}: {e.code} {e.read().decode()[:300]}") from e


def repos():
    page = 1
    while True:
        batch = api("GET", f"/orgs/{ORG}/repos?type=all&per_page=100&page={page}")
        if not batch:
            return
        yield from (r for r in batch if not r["archived"] and r["name"] != SELF
                    and r["name"] not in EXCLUDE)
        page += 1


def get_file(repo, path, ref):
    return api("GET", f"/repos/{ORG}/{repo}/contents/{path}?ref={ref}", ok404=True)


def delete_direct(repo, default, path, sha):
    """Delete a config directly on the default branch; None on success, reason if blocked."""
    try:
        api("DELETE", f"/repos/{ORG}/{repo}/contents/{path}",
            {"message": f"chore: drop {path} (central CodeRabbit config)", "branch": default,
             "sha": sha})
        return None
    except RuntimeError as e:
        return str(e)


def sync(repo, default, content):
    log = []
    cur = get_file(repo, TARGET, default)
    # 1) Own configs that differ from central, and stray variants: direct delete on default.
    pending = []  # deletions that were blocked and go into the PR instead
    targets = [(TARGET, cur)] if cur and base64.b64decode(cur["content"]) != content else []
    targets += [(p, f) for p in STRAY if (f := get_file(repo, p, default))]
    for path, f in targets:
        reason = delete_direct(repo, default, path, f["sha"])
        if reason:
            log.append(f"DIRECT-DELETE-BLOCKED {path}: {reason}")
            pending.append(path)
        else:
            log.append(f"DELETED-DIRECT {path}")
    cur = get_file(repo, TARGET, default)
    need_put = not cur or base64.b64decode(cur["content"]) != content
    if not need_put and not pending:
        return "; ".join(log + ["QUIET up to date"])
    # 2) Central quiet config (plus blocked deletions) via PR with auto-merge.
    sha = api("GET", f"/repos/{ORG}/{repo}/git/ref/heads/{default}")["object"]["sha"]
    if api("GET", f"/repos/{ORG}/{repo}/git/ref/heads/{BRANCH}", ok404=True):
        api("PATCH", f"/repos/{ORG}/{repo}/git/refs/heads/{BRANCH}", {"sha": sha, "force": True})
    else:
        api("POST", f"/repos/{ORG}/{repo}/git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": sha})
    for path in pending:
        if path == TARGET:
            continue  # overwritten below
        f = get_file(repo, path, BRANCH)
        api("DELETE", f"/repos/{ORG}/{repo}/contents/{path}",
            {"message": f"chore: drop {path} (central CodeRabbit config)", "branch": BRANCH,
             "sha": f["sha"]})
    f = get_file(repo, TARGET, BRANCH)
    body = {"message": TITLE, "branch": BRANCH, "content": base64.b64encode(content).decode()}
    if f:
        body["sha"] = f["sha"]
    api("PUT", f"/repos/{ORG}/{repo}/contents/{TARGET}", body)
    pulls = api("GET", f"/repos/{ORG}/{repo}/pulls?state=open&head={ORG}:{BRANCH}")
    if pulls:
        return "; ".join(log + [f"QUIET-PR updated {pulls[0]['html_url']}"])
    pr = api("POST", f"/repos/{ORG}/{repo}/pulls",
             {"title": TITLE, "head": BRANCH, "base": default, "body": BODY})
    res = subprocess.run(["gh", "pr", "merge", str(pr["number"]), "--auto", "--squash",
                          "-R", f"{ORG}/{repo}"], capture_output=True, text=True)
    note = "" if res.returncode == 0 else f" (auto-merge not enabled: {res.stderr.strip()})"
    return "; ".join(log + [f"QUIET-PR opened {pr['html_url']}{note}"])


def main():
    with open(TARGET, "rb") as f:
        content = f.read()
    failed = False
    for r in repos():
        try:
            print(f"{r['name']}: {sync(r['name'], r['default_branch'], content)}")
        except Exception as e:  # keep going, report at the end
            failed = True
            print(f"::error::{r['name']}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
