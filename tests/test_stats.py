import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import check  # noqa: E402
import stats  # noqa: E402

REPO = "https://github.com/someone/az-mods"


def rel(*assets):
    return {"assets": [{"name": n, "download_count": c} for n, c in assets]}


class Counting(unittest.TestCase):
    def test_versions_add_up_per_id(self):
        r = [rel(("beat-counter-1.0.0.azmod", 10), ("beat-counter-1.0.0-icon.png", 99)),
             rel(("beat-counter-1.1.0.azmod", 5), ("deck-overview-1.0.0.azmod", 3))]
        self.assertEqual(stats.counts_from_releases(r), {"beat-counter": 15, "deck-overview": 3})

    def test_what_is_not_a_package_is_not_counted(self):
        r = [rel(("beat-counter-1.0.azmod", 7), ("Beat-Counter-1.0.0.azmod", 7), ("beat-counter-1.0.0.zip", 7),
                 ("beat-counter-01.0.0.azmod", 7), ("x-1.0.0.azmod", 7)),
             {"assets": [{"name": "beat-counter-1.0.0.azmod", "download_count": "7"},
                         {"name": "beat-counter-1.0.0.azmod", "download_count": True},
                         {"name": "beat-counter-1.0.0.azmod", "download_count": -1}]}]
        self.assertEqual(stats.counts_from_releases(r), {})

    def test_pages_are_followed_until_a_short_one(self):
        pages = {1: [rel(("a-mod-1.0.0.azmod", 1))] * 100, 2: [rel(("a-mod-1.0.0.azmod", 1))] * 3}
        seen = []

        def get(url):
            p = int(url.rsplit("page=", 1)[1])
            seen.append(p)
            return pages.get(p, [])
        self.assertEqual(stats.counts_from_releases(stats.repo_releases(REPO, get)), {"a-mod": 103})
        self.assertEqual(seen, [1, 2])

    def test_a_repository_that_cannot_be_read_keeps_its_last_counts(self):
        def get(url):
            raise OSError("HTTP 502")
        mods, problems = stats.collect([REPO], {REPO: {"beat-counter": 40}}, get)
        self.assertEqual(mods, {REPO: {"beat-counter": 40}})
        self.assertEqual(len(problems), 1)

    def test_CONTROL_a_readable_repository_takes_its_new_counts(self):
        def get(url):
            return [rel(("beat-counter-1.0.0.azmod", 41))]
        mods, problems = stats.collect([REPO], {REPO: {"beat-counter": 40}}, get)
        self.assertEqual(mods, {REPO: {"beat-counter": 41}})
        self.assertEqual(problems, [])


class Writing(unittest.TestCase):
    def run_main(self, counts, existing=None):
        d = tempfile.mkdtemp()
        lst, out = os.path.join(d, "list.json"), os.path.join(d, "stats.json")
        json.dump({"azmods_repos": 1, "repos": [REPO]}, open(lst, "w"))
        if existing is not None:
            json.dump(existing, open(out, "w"))
        saved = stats.api_get
        stats.api_get = lambda url: [rel(*[(f"{i}-1.0.0.azmod", n) for i, n in counts.items()])]
        try:
            self.assertEqual(stats.main([lst, out]), 0)
        finally:
            stats.api_get = saved
        return out

    def test_written_and_valid_for_the_check(self):
        out = self.run_main({"beat-counter": 12})
        raw = open(out, "rb").read()
        d = json.loads(raw)
        self.assertEqual(d["mods"], {REPO: {"beat-counter": 12}})
        self.assertEqual(check.check_stats(d, len(raw)), [])

    def test_nothing_changed_nothing_rewritten(self):
        old = {"azmods_stats": 1, "generated": "2000-01-01T00:00Z", "mods": {REPO: {"beat-counter": 12}}}
        out = self.run_main({"beat-counter": 12}, old)
        self.assertEqual(json.load(open(out))["generated"], "2000-01-01T00:00Z")

    def test_CONTROL_a_changed_count_is_rewritten(self):
        old = {"azmods_stats": 1, "generated": "2000-01-01T00:00Z", "mods": {REPO: {"beat-counter": 12}}}
        out = self.run_main({"beat-counter": 13}, old)
        d = json.load(open(out))
        self.assertNotEqual(d["generated"], "2000-01-01T00:00Z")
        self.assertEqual(d["mods"][REPO]["beat-counter"], 13)


class StatsCheck(unittest.TestCase):
    def good(self):
        return {"azmods_stats": 1, "generated": "2026-01-01T00:00Z", "mods": {REPO: {"beat-counter": 5}}}

    def test_a_good_file_passes(self):
        self.assertEqual(check.check_stats(self.good()), [])

    def test_each_rule_is_checked(self):
        bad = []
        for k, v in (("azmods_stats", 2), ("generated", "yesterday"), ("mods", [])):
            d = self.good()
            d[k] = v
            bad.append(d)
        for mods in ({"http://github.com/a/b": {"x-mod": 1}}, {REPO: {"X": 1}}, {REPO: {"x-mod": -1}},
                     {REPO: {"x-mod": 10 ** 13}}, {REPO: {"x-mod": True}}, {REPO: {"x-mod": "1"}}, {REPO: [1]}):
            d = self.good()
            d["mods"] = mods
            bad.append(d)
        for d in bad:
            self.assertNotEqual(check.check_stats(d), [], d)
        self.assertNotEqual(check.check_stats(self.good(), check.STATS_BYTES + 1), [])
        many = self.good()
        many["mods"] = {REPO: {f"mod-{i:05d}": 1 for i in range(check.STATS_ROWS + 1)}}
        self.assertNotEqual(check.check_stats(many), [])


if __name__ == "__main__":
    unittest.main()
