#!/usr/bin/env python3
"""Download counts for the listed mods, into stats.json.

    python3 tools/stats.py azmods-repos.json stats.json

For each repository on the list, every release asset named <id>-<version>.azmod counts
toward <id>: the counts of all its versions are added up (downloads from decks, from the
desktop app and by hand alike). The result:

    {"azmods_stats": 1, "generated": "YYYY-MM-DDTHH:MMZ",
     "mods": {"https://github.com/OWNER/REPO": {"<id>": <downloads>, ...}, ...}}

A repository whose releases cannot be read keeps the counts it had in the previous
stats.json, so a passing failure never shows a mod with fewer downloads. The file is
rewritten only when a count changed, so the scheduled run commits nothing when nothing
moved. Decks fetch this file with the list; they never call the GitHub API themselves.

GITHUB_TOKEN, when set, is sent with each request (the workflow's own token).
"""
import datetime
import json
import os
import re
import sys
import urllib.request

ASSET_RE = re.compile(r"([a-z0-9-]{3,32})-(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.azmod")
REPO_RE = re.compile(r"https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)")
MAX_PAGES = 20   # 100 releases a page: 2000 releases per repository at most


def counts_from_releases(releases):
    """{id: downloads} from a list of GitHub release objects."""
    out = {}
    for rel in releases:
        for a in rel.get("assets") or []:
            m = ASSET_RE.fullmatch(str(a.get("name", "")))
            n = a.get("download_count")
            if not m or not isinstance(n, int) or isinstance(n, bool) or n < 0:
                continue
            out[m.group(1)] = out.get(m.group(1), 0) + n
    return out


def api_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "az-mods-index-stats"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def repo_releases(repo, get=None):
    get = get or api_get
    m = REPO_RE.fullmatch(repo)
    if not m:
        raise ValueError("not a GitHub repository address")
    out = []
    for page in range(1, MAX_PAGES + 1):
        batch = get(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}/releases?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("the releases are not a list")
        out += batch
        if len(batch) < 100:
            break
    return out


def collect(repos, previous, get=None):
    """{repo: {id: downloads}} for every listed repository with a count; a repository that
    cannot be read keeps its previous counts. Returns (mods, problems)."""
    mods, problems = {}, []
    for repo in repos:
        try:
            c = counts_from_releases(repo_releases(repo, get))
        except Exception as ex:   # any failure: that repository's last counts stand
            problems.append(f"{repo}: releases could not be read ({ex})")
            c = previous.get(repo, {})
        if c:
            mods[repo] = dict(sorted(c.items()))
    return mods, problems


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    lst = json.load(open(argv[0], encoding="utf-8"))
    repos = lst.get("repos", []) if isinstance(lst, dict) else []
    try:
        old = json.load(open(argv[1], encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    previous = old.get("mods", {}) if isinstance(old, dict) and isinstance(old.get("mods"), dict) else {}
    mods, problems = collect(repos, previous)
    for p in problems:
        print("::warning::" + p)
    if mods == previous and old:
        print(f"{sum(len(v) for v in mods.values())} mods, no count changed")
        return 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    out = {"azmods_stats": 1, "generated": stamp, "mods": dict(sorted(mods.items()))}
    with open(argv[1], "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    print(f"{sum(len(v) for v in mods.values())} mods counted, written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
