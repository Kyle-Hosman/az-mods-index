#!/usr/bin/env python3
"""Download counts for the mods on the community list, as stats.json.

    python3 tools/stats.py azmods-repos.json stats.json

For each listed repository it reads azmods-repo.json (the mods it offers) and the repository's
releases from the GitHub API, and sums, for each mod, the download count of every release asset
named <id>-<MAJOR.MINOR.PATCH>.azmod: the mod's package, over all its versions. Icons and other
assets do not count. GitHub counts every download of the file: from decks, the desktop app, or by
hand, updates and reinstalls included.

stats.json:

    {"azmods_stats": 1, "generated": "YYYY-MM-DDTHH:MMZ",
     "mods": {"https://github.com/OWNER/REPO": {"<mod id>": <downloads>}}}

The file is written only when a number changed, so a scheduled run commits nothing on a quiet
day. A repository that cannot be read keeps the counts it had. The token in GITHUB_TOKEN, when
set, is sent to the API (a scheduled workflow has one), which allows 1000 requests an hour; each
repository costs one request per 100 releases.
"""
import datetime
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

ASSET_RE = re.compile(r"(?P<id>.+)-(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.azmod")
API = "https://api.github.com/repos/"
MAX_PAGES = 20   # 2000 releases per repository: far past any real one


def mod_ids(idx):
    """The mod ids a repository's azmods-repo.json offers."""
    mods = idx.get("mods") if isinstance(idx, dict) else None
    return {e["id"] for e in mods if isinstance(e, dict) and isinstance(e.get("id"), str)} if isinstance(mods, list) else set()


def count(releases, ids):
    """{id: downloads} over every release's .azmod assets, for the ids offered (each counted, 0 too)."""
    out = {i: 0 for i in ids}
    for rel in releases if isinstance(releases, list) else []:
        assets = rel.get("assets") if isinstance(rel, dict) else None
        for a in assets if isinstance(assets, list) else []:
            if not isinstance(a, dict) or not isinstance(a.get("name"), str):
                continue
            m = ASSET_RE.fullmatch(a["name"])
            n = a.get("download_count")
            if m and m.group("id") in out and isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                out[m.group("id")] += n
    return out


def build(repos, fetch_index, fetch_releases, previous, log=print):
    """The "mods" object: each repository's counts, or its previous ones when it cannot be read."""
    mods = {}
    for r in repos:
        try:
            ids = mod_ids(fetch_index(r))
            mods[r] = count(fetch_releases(r), ids)
        except Exception as ex:   # any failure: this repository keeps what it had
            log(f"::warning::{r}: not counted ({ex}); its previous counts are kept")
            if isinstance(previous.get(r), dict):
                mods[r] = previous[r]
    return mods


def fetch_releases(repo, token=None, opener=urllib.request.urlopen):
    owner_repo = repo[len("https://github.com/"):]
    out = []
    for page in range(1, MAX_PAGES + 1):
        req = urllib.request.Request(f"{API}{owner_repo}/releases?per_page=100&page={page}",
                                     headers={"Accept": "application/vnd.github+json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with opener(req, timeout=30) as resp:
            batch = json.loads(resp.read(16 << 20).decode("utf-8"))
        if not isinstance(batch, list):
            raise ValueError("the releases list is not a JSON list")
        out += batch
        if len(batch) < 100:
            break
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    lst = json.load(open(argv[0], encoding="utf-8"))
    errs = check.check_list(lst)
    if errs:
        for e in errs:
            print("::error::" + e)
        return 1
    previous = {}
    if os.path.exists(argv[1]):
        try:
            old = json.load(open(argv[1], encoding="utf-8"))
            if not check.check_stats(old):
                previous = old["mods"]
        except ValueError:
            pass
    token = os.environ.get("GITHUB_TOKEN")
    mods = build(lst["repos"], lambda r: check.fetch_json(check.raw_index_url(r)),
                 lambda r: fetch_releases(r, token), previous)
    if mods == previous:
        print(f"{len(mods)} repositories: no count changed")
        return 0
    out = {"azmods_stats": 1,
           "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "mods": mods}
    errs = check.check_stats(out)
    if errs:
        for e in errs:
            print("::error::" + e)
        return 1
    with open(argv[1] + ".new", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(argv[1] + ".new", argv[1])
    print(f"{len(mods)} repositories, {sum(len(v) for v in mods.values())} mods counted")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
