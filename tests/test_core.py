"""Run with:  python -m unittest discover tests   (no Qt needed)."""
import gzip
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cherrylogs.filters import Filters, apply_filters  # noqa: E402
from cherrylogs.parser import parse_file  # noqa: E402
from cherrylogs.stats import compute_stats  # noqa: E402
from cherrylogs.storage import Storage, file_sha256  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.log")


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.gz = os.path.join(self.tmp, "2024-05-12-1.log.gz")
        with open(SAMPLE, "rb") as a, gzip.open(self.gz, "wb") as b:
            shutil.copyfileobj(a, b)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parse_split_and_players(self):
        r = parse_file(self.gz)
        cats = {c: sum(e.category == c for e in r.entries)
                for c in ("server", "command", "chat")}
        self.assertEqual(cats, {"server": 14, "command": 3, "chat": 3})
        self.assertEqual(r.log_date, "2024-05-12")
        players = {p for e in r.entries for p in e.players}
        self.assertEqual(players, {"Steve", "Alex"})

    def test_midnight_rollover(self):
        r = parse_file(self.gz)
        self.assertEqual(r.entries[-1].ts.strftime("%Y-%m-%d"), "2024-05-13")

    def test_multiline_stacktrace_is_merged(self):
        r = parse_file(self.gz)
        err = [e for e in r.entries if e.event == "error"][0]
        self.assertIn("NullPointerException", err.message)

    def test_player_filter_and_stats(self):
        r = parse_file(self.gz)
        res = apply_filters(r.entries, Filters(players=frozenset({"Steve"})))
        self.assertTrue(all("Steve" in e.players for e in res.everything))
        stats, _ = compute_stats(res.base, [], frozenset({"Steve"}))
        self.assertEqual(stats["Steve"].messages, 1)
        self.assertEqual(stats["Steve"].commands, 1)
        self.assertEqual(int(stats["Steve"].playtime), 408)

    def test_storage_roundtrip_and_dedupe(self):
        r = parse_file(self.gz)
        st = Storage(os.path.join(self.tmp, "t.db"))
        sha = file_sha256(self.gz)
        iid = st.add_import("x.gz", self.gz, sha, 1, r)
        self.assertEqual(st.find_import_by_hash(sha), iid)
        self.assertEqual(len(st.load_entries([iid])), len(r.entries))
        st.delete_imports([iid])
        self.assertEqual(st.load_entries([iid]), [])
        st.close()


if __name__ == "__main__":
    unittest.main()
