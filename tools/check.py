#!/usr/bin/env python3
"""Checks for azmods-repos.json that need nothing but Python, so they run even when the
SDK's azmod-pack is not available.

    python3 tools/check.py azmods-repos.json            the list's schema
    python3 tools/check.py azmods-repos.json --fetch    and every listed repository's
                                                        azmods-repo.json: each mod's
                                                        version and min_core, and that
                                                        no mod id is listed twice

A deck compares versions as MAJOR.MINOR.PATCH, numbers only, each 0 to 9999: an update
is offered only when the listed version is higher than the installed one, and anything
else (1.2, 1.0.0-beta.1) is never offered as an update. min_core is compared the same
way, and an entry with any other min_core is skipped. azmod-pack applies the same rule.

A mod id names one folder on the USB stick and the mod's settings and files on the deck, so
two mods with the same id cannot both be installed, and a deck shows only one of them. Every
id on the community list is therefore unique across all listed repositories (compared
without regard to case). Two mods with the same display name but different ids are allowed;
that is a warning, since a DJ tells them apart only by their authors.

    python3 tools/check.py --stats stats.json           the download counts' file
                                                        (tools/stats.py) within what a
                                                        deck reads: a deck drops anything
                                                        outside these limits
"""
import json
import re
import sys
import urllib.request

REPO_RE = re.compile(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
VERSION_RE = re.compile(r"(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})")
MAX_REPOS = 64   # the deck reads the first 64 listed repositories
ID_RE = re.compile(r"[a-z0-9-]{3,32}")
STATS_BYTES = 262144   # a deck downloads at most this much of stats.json
STATS_ROWS = 16384     # and keeps at most this many counts
STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z")


def check_list(d):
    """Problems with the list itself, as a list of strings."""
    errs = []
    if not isinstance(d, dict):
        return ["the file must be a JSON object"]
    if d.get("azmods_repos") != 1:
        errs.append('"azmods_repos" must be 1')
    repos = d.get("repos")
    if not isinstance(repos, list):
        errs.append('"repos" must be a list')
        repos = []
    for r in repos:
        if not isinstance(r, str) or not REPO_RE.fullmatch(r) or r.endswith(".git"):
            errs.append(f"not https://github.com/OWNER/REPO: {r!r}")
    if len(repos) > MAX_REPOS:
        errs.append(f"{len(repos)} repositories: the deck reads at most {MAX_REPOS}")
    if len(set(str(r).lower() for r in repos)) != len(repos):   # GitHub ignores case in owner/name
        errs.append("a repository is listed twice")
    if all(isinstance(r, str) for r in repos) and repos != sorted(repos, key=str.lower):
        errs.append("keep the list sorted")
    return errs


def check_index(idx, where):
    """Version problems in one repository's azmods-repo.json."""
    if not isinstance(idx, dict) or not isinstance(idx.get("mods"), list):
        return [f"{where}: not an azmods-repo.json (no \"mods\" list)"]
    errs = []
    for n, e in enumerate(idx["mods"]):
        if not isinstance(e, dict):
            errs.append(f"{where}: mods[{n}] is not an object")
            continue
        name = e.get("id", f"mods[{n}]")
        v = e.get("version")
        if not isinstance(v, str) or not VERSION_RE.fullmatch(v):
            errs.append(f"{where}: {name}: \"version\" {v!r} is not MAJOR.MINOR.PATCH (numbers only, each 0-9999)")
        mc = e.get("min_core")
        if mc is not None and (not isinstance(mc, str) or not VERSION_RE.fullmatch(mc)):
            errs.append(f"{where}: {name}: \"min_core\" {mc!r} is not MAJOR.MINOR.PATCH")
    return errs


def check_ids(indexes):
    """Ids across the listed repositories. indexes: [(repo, azmods-repo.json), ...] in list
    order. Returns (errors, warnings): an id offered twice is an error; the same display
    name under different ids is a warning."""
    errs, warns = [], []
    by_id, by_name = {}, {}
    for repo, idx in indexes:
        mods = idx.get("mods") if isinstance(idx, dict) else None
        for e in mods if isinstance(mods, list) else []:
            if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                continue
            by_id.setdefault(e["id"].lower(), []).append((repo, e["id"]))
            if isinstance(e.get("name"), str) and e["name"].strip():
                by_name.setdefault(e["name"].strip().casefold(), []).append((repo, e["id"], e["name"]))
    for key, seen in by_id.items():
        if len(seen) > 1:
            where = ", ".join(f"{r} ({i})" for r, i in seen)
            errs.append(f"mod id {seen[0][1]!r} is used more than once: {where}. "
                        "Every id on the community list must be unique; the later one needs a new id")
    for key, seen in by_name.items():
        ids = {i.lower() for _, i, _ in seen}
        if len(ids) > 1:
            where = ", ".join(f"{i} in {r}" for r, i, _ in seen)
            warns.append(f"several mods are named {seen[0][2]!r} ({where}): the deck tells them apart "
                         "only by author")
    return errs, warns


def check_stats(d, size=0):
    """problems with a stats.json (tools/stats.py) a deck would read"""
    errs = []
    if size > STATS_BYTES:
        errs.append(f"stats.json: {size} bytes, more than the {STATS_BYTES} a deck reads")
    if not isinstance(d, dict) or d.get("azmods_stats") != 1:
        return errs + ['stats.json: "azmods_stats" must be 1']
    if not isinstance(d.get("generated"), str) or not STAMP_RE.fullmatch(d["generated"]):
        errs.append('stats.json: "generated" must be YYYY-MM-DDTHH:MMZ')
    mods = d.get("mods")
    if not isinstance(mods, dict):
        return errs + ['stats.json: "mods" must be an object']
    rows = 0
    for repo, ids in mods.items():
        if not REPO_RE.fullmatch(repo) or len(repo) > 300:
            errs.append(f"stats.json: {repo!r} is not a https://github.com/OWNER/REPO address")
        if not isinstance(ids, dict):
            errs.append(f"stats.json: {repo}: must map mod ids to counts")
            continue
        for i, n in ids.items():
            rows += 1
            if not ID_RE.fullmatch(i):
                errs.append(f"stats.json: {repo}: {i!r} is not a mod id")
            if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n < 10 ** 13:
                errs.append(f"stats.json: {repo}: {i}: the count must be a whole number of at most 13 digits")
    if rows > STATS_ROWS:
        errs.append(f"stats.json: {rows} counts, more than the {STATS_ROWS} a deck keeps")
    return errs


def raw_index_url(repo):
    return repo.replace("https://github.com/", "https://raw.githubusercontent.com/", 1) + "/HEAD/azmods-repo.json"


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read(262145).decode("utf-8"))


def main(argv):
    if len(argv) == 2 and argv[0] == "--stats":
        raw = open(argv[1], "rb").read()
        try:
            errs = check_stats(json.loads(raw.decode("utf-8")), len(raw))
        except ValueError as ex:
            errs = [f"stats.json: not JSON ({ex})"]
        for e in errs:
            print("::error::" + e)
        print(f"stats.json: {len(errs)} problems")
        return 1 if errs else 0
    if not argv or argv[0].startswith("-"):
        print(__doc__.strip())
        return 2
    d = json.load(open(argv[0], encoding="utf-8"))
    errs = check_list(d)
    repos = d.get("repos") if isinstance(d, dict) and isinstance(d.get("repos"), list) else []
    warns = []
    if "--fetch" in argv[1:] and not errs:
        indexes = []
        for r in repos:
            try:
                idx = fetch_json(raw_index_url(r))
            except Exception as ex:   # any failure to read it is a problem with that repository
                errs.append(f"{r}: azmods-repo.json could not be read ({ex})")
                continue
            errs += check_index(idx, r)
            indexes.append((r, idx))
        e2, warns = check_ids(indexes)
        errs += e2
    for w in warns:
        print("::warning::" + w)
    for e in errs:
        print("::error::" + e)
    print(f"{len(repos)} repositories, {len(errs)} problems")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
