import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import check  # noqa: E402


def entry(**kw):
    e = {"id": "beat-counter", "version": "1.0.0"}
    e.update(kw)
    return e


class ListSchema(unittest.TestCase):
    def test_the_published_list_passes(self):
        here = os.path.join(os.path.dirname(__file__), "..", "azmods-repos.json")
        import json
        self.assertEqual(check.check_list(json.load(open(here))), [])

    def test_schema_problems(self):
        good = "https://github.com/someone/az-mods"
        self.assertEqual(check.check_list({"azmods_repos": 1, "repos": [good]}), [])
        for bad in ({"azmods_repos": 2, "repos": []},
                    {"azmods_repos": 1, "repos": [good + ".git"]},
                    {"azmods_repos": 1, "repos": [good + "/"]},
                    {"azmods_repos": 1, "repos": [good, good]},
                    {"azmods_repos": 1, "repos": ["https://github.com/Someone/az-mods", good]},
                    {"azmods_repos": 1, "repos": ["https://github.com/b/x", "https://github.com/a/x"]},
                    {"azmods_repos": 1, "repos": ["https://github.com/o/r%02d" % i for i in range(65)]}):
            self.assertNotEqual(check.check_list(bad), [], bad)


class Versions(unittest.TestCase):
    def test_versions_the_deck_compares(self):
        for good in ("0.0.0", "1.2.3", "9999.9999.9999"):
            self.assertEqual(check.check_index({"mods": [entry(version=good)]}, "r"), [], good)

    def test_versions_the_deck_cannot_compare(self):
        for bad in ("1.2", "1.0.0-beta.1", "1.0.0+build", "v1.0.0", "01.0.0", "1.0.10000", "", 1, None):
            errs = check.check_index({"mods": [entry(version=bad)]}, "r")
            self.assertTrue(errs and "MAJOR.MINOR.PATCH" in errs[0], (bad, errs))

    def test_min_core(self):
        self.assertEqual(check.check_index({"mods": [entry(min_core="1.2.3")]}, "r"), [])
        self.assertNotEqual(check.check_index({"mods": [entry(min_core="1.3")]}, "r"), [])

    def test_raw_url(self):
        self.assertEqual(check.raw_index_url("https://github.com/someone/az-mods"),
                         "https://raw.githubusercontent.com/someone/az-mods/HEAD/azmods-repo.json")


class Ids(unittest.TestCase):
    A, B = "https://github.com/alice/mods", "https://github.com/bob/mods"

    def idx(self, *mods):
        return {"mods": [entry(**m) for m in mods]}

    def test_the_same_id_in_two_repositories_is_refused(self):
        errs, _ = check.check_ids([(self.A, self.idx({"id": "beat-counter"})), (self.B, self.idx({"id": "beat-counter"}))])
        self.assertEqual(len(errs), 1)
        self.assertIn("beat-counter", errs[0])
        self.assertIn(self.A, errs[0])
        self.assertIn(self.B, errs[0])

    def test_ids_compare_without_case(self):
        errs, _ = check.check_ids([(self.A, self.idx({"id": "beat-counter"})), (self.B, self.idx({"id": "Beat-Counter"}))])
        self.assertEqual(len(errs), 1)

    def test_the_same_id_twice_in_one_repository_is_refused(self):
        errs, _ = check.check_ids([(self.A, self.idx({"id": "beat-counter"}, {"id": "beat-counter"}))])
        self.assertEqual(len(errs), 1)

    def test_distinct_ids_pass(self):   # the control for the three above
        errs, warns = check.check_ids([(self.A, self.idx({"id": "beat-counter", "name": "Beat Counter"})),
                                       (self.B, self.idx({"id": "bob-loops", "name": "Loops"}))])
        self.assertEqual((errs, warns), ([], []))

    def test_the_same_name_under_two_ids_is_a_warning(self):
        errs, warns = check.check_ids([(self.A, self.idx({"id": "beat-counter", "name": "Beat Counter"})),
                                       (self.B, self.idx({"id": "bob-beat-counter", "name": "beat counter"}))])
        self.assertEqual(errs, [])
        self.assertEqual(len(warns), 1)
        self.assertIn("by author", warns[0])

    def test_main_reports_a_duplicate_id_from_the_listed_repositories(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        pages = {check.raw_index_url(self.A): self.idx({"id": "beat-counter"}),
                 check.raw_index_url(self.B): self.idx({"id": "beat-counter"})}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"azmods_repos": 1, "repos": [self.A, self.B]}, f)
        orig = check.fetch_json
        check.fetch_json = lambda url: pages[url]
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = check.main([f.name, "--fetch"])
            self.assertEqual(rc, 1)
            self.assertIn("::error::mod id 'beat-counter'", out.getvalue())
            pages[check.raw_index_url(self.B)] = self.idx({"id": "bob-counter"})
            with redirect_stdout(io.StringIO()):
                self.assertEqual(check.main([f.name, "--fetch"]), 0)   # CONTROL: distinct ids pass
        finally:
            check.fetch_json = orig
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
