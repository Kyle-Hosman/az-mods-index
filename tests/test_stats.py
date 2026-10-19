import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import check  # noqa: E402
import stats  # noqa: E402

REPO = "https://github.com/someone/az-mods"
OTHER = "https://github.com/else/az-tools"


def asset(name, n):
    return {"name": name, "download_count": n}


def index(*ids):
    return {"azmods_repo": 1, "mods": [{"id": i, "version": "1.0.0"} for i in ids]}


class Count(unittest.TestCase):
    def test_every_version_of_a_package_counts(self):
        rels = [{"assets": [asset("beat-counter-1.1.0.azmod", 30), asset("beat-counter-1.1.0-icon.png", 900)]},
                {"assets": [asset("beat-counter-1.0.0.azmod", 12)]}]
        self.assertEqual(stats.count(rels, {"beat-counter"}), {"beat-counter": 42})

    def test_only_packages_of_offered_mods(self):
        rels = [{"assets": [asset("beat-counter-1.0.0.azmod", 5), asset("old-mod-1.0.0.azmod", 7),
                            asset("beat-counter.azmod", 3), asset("beat-counter-1.0.azmod", 3),
                            asset("beat-counter-1.0.0.zip", 3), asset("notes.txt", 3)]}]
        self.assertEqual(stats.count(rels, {"beat-counter"}), {"beat-counter": 5})

    def test_an_id_with_dashes_and_digits(self):
        rels = [{"assets": [asset("eq-kill-2-2.10.3.azmod", 4), asset("eq-kill-2.0.0.azmod", 6)]}]
        self.assertEqual(stats.count(rels, {"eq-kill-2", "eq-kill"}), {"eq-kill-2": 4, "eq-kill": 6})

    def test_a_mod_never_downloaded_counts_zero(self):
        self.assertEqual(stats.count([], {"set-clock"}), {"set-clock": 0})

    def test_damaged_api_answers_add_nothing(self):
        rels = [None, {"assets": None}, {"assets": [None, {"name": 3}, asset("a-b-1.0.0.azmod", -1),
                                                     asset("a-b-1.0.0.azmod", True), asset("a-b-1.0.0.azmod", "9")]}]
        self.assertEqual(stats.count(rels, {"a-b"}), {"a-b": 0})
        self.assertEqual(stats.count({"message": "rate limited"}, {"a-b"}), {"a-b": 0})


class Build(unittest.TestCase):
    def test_a_repository_that_cannot_be_read_keeps_its_counts(self):
        def fetch_index(r):
            if r == OTHER:
                raise OSError("timed out")
            return index("beat-counter")

        def fetch_rel(r):
            return [{"assets": [asset("beat-counter-1.0.0.azmod", 9)]}]

        logs = []
        prev = {OTHER: {"pad-tools": 77}}
        mods = stats.build([REPO, OTHER], fetch_index, fetch_rel, prev, logs.append)
        self.assertEqual(mods, {REPO: {"beat-counter": 9}, OTHER: {"pad-tools": 77}})
        self.assertTrue(any("not counted" in m for m in logs))

    def test_a_repository_never_counted_and_unreadable_is_left_out(self):
        def boom(r):
            raise OSError("404")

        self.assertEqual(stats.build([REPO], boom, boom, {}, lambda m: None), {})


class Schema(unittest.TestCase):
    def good(self):
        return {"azmods_stats": 1, "generated": "2019-04-02T06:41Z", "mods": {REPO: {"beat-counter": 42}}}

    def test_good(self):
        self.assertEqual(check.check_stats(self.good()), [])
        self.assertEqual(check.check_stats(dict(self.good(), mods={})), [])

    def test_problems(self):
        for change in ({"azmods_stats": 2}, {"generated": "2019-04-02 06:41"}, {"generated": None},
                       {"mods": []}, {"mods": {REPO + ".git": {}}}, {"mods": {"https://example.com/a/b": {}}},
                       {"mods": {REPO: []}}, {"mods": {REPO: {"Beat_Counter": 1}}}, {"mods": {REPO: {"ab": 1}}},
                       {"mods": {REPO: {"beat-counter": -1}}}, {"mods": {REPO: {"beat-counter": 1.5}}},
                       {"mods": {REPO: {"beat-counter": True}}}, {"mods": {REPO: {"beat-counter": 10 ** 13}}},
                       {"mods": {"https://github.com/o/r%02d" % i: {} for i in range(65)}}):
            d = dict(self.good(), **change)
            self.assertNotEqual(check.check_stats(d), [], change)
        self.assertNotEqual(check.check_stats([]), [])


class Main(unittest.TestCase):
    def test_written_only_when_a_count_changes(self):
        d = tempfile.mkdtemp()
        lst = os.path.join(d, "list.json")
        out = os.path.join(d, "stats.json")
        json.dump({"azmods_repos": 1, "repos": [REPO]}, open(lst, "w"))
        counts = {"n": 5}
        real_fetch, real_rel = check.fetch_json, stats.fetch_releases
        check.fetch_json = lambda url: index("beat-counter")
        stats.fetch_releases = lambda r, token=None: [{"assets": [asset("beat-counter-1.0.0.azmod", counts["n"])]}]
        try:
            self.assertEqual(stats.main([lst, out]), 0)
            first = json.load(open(out))
            self.assertEqual(check.check_stats(first), [])
            self.assertEqual(first["mods"], {REPO: {"beat-counter": 5}})
            os.utime(out, (1, 1))
            self.assertEqual(stats.main([lst, out]), 0)
            self.assertEqual(os.stat(out).st_mtime, 1, "rewritten although nothing changed")
            counts["n"] = 6
            self.assertEqual(stats.main([lst, out]), 0)
            self.assertEqual(json.load(open(out))["mods"], {REPO: {"beat-counter": 6}})
        finally:
            check.fetch_json, stats.fetch_releases = real_fetch, real_rel

    def test_a_bad_list_writes_nothing(self):
        d = tempfile.mkdtemp()
        lst = os.path.join(d, "list.json")
        out = os.path.join(d, "stats.json")
        json.dump({"azmods_repos": 2, "repos": []}, open(lst, "w"))
        self.assertEqual(stats.main([lst, out]), 1)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
