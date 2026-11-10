"""A count is read as the screen shows it, or refused naming the cell.

Instagram shows counts abbreviated ("412K", "1.2M"; in pt-BR "412 mil",
"1,2 mi"), and that is what a person copies off the profile. swipe.py used to
drop every character that is not a digit: "1.2M" became 12, "1e5" became 15,
and the ranking went to swipe.md with numbers nobody measured. Now a cell is a
count it can read, or the run stops with exit 2 naming the line, the column
and the cell: a wrong number is never a result.

Every column swipe reads as a count (COUNT_COLUMNS) runs through every case;
the numbers are written by hand. A digit-stripping read anywhere else in
swipe.py fails the guard at the end."""

import json
import os
import re
import unittest

from _support import SKILLS, TOOLS, load, run_tool

sw = load("swipe")

READ = {
    "en": [("412K", 412000), ("1.2M", 1200000), ("2.5k", 2500), ("1B", 1000000000),
           ("1,234", 1234), ("48,000", 48000), ("1.234.567", 1234567), ("412000", 412000),
           ("1.2 M", 1200000)],
    "pt-BR": [("412 mil", 412000), ("1,2 mi", 1200000), ("12 mil", 12000), ("2,5 mil", 2500),
              ("1 bi", 1000000000), ("1.234", 1234), ("48.000", 48000), ("1.234.567", 1234567),
              ("412000", 412000), ("3K", 3000)],
}
REFUSED = {
    "en": ["1e5", "1,5", "12.34", "abc", "412K views", "12 mil", "1,2 mi", "1.2.3M", "-5"],
    "pt-BR": ["1e5", "1,5", "abc", "1.2M", "412K views", "1,2 milhões", "12,34"],
}


def tsv(views="400000", followers="", median="10000"):
    return ("account\tfollowers\tmedian\tviews\thook\n"
            f"@a\t{followers}\t{median}\t{views}\tnobody tells you that your first 30 reels flop\n"
            "@b\t\t10000\t20000\tin this video I am going to show you my routine\n")


def cell(column, value):
    kw = {"views": "400000", "followers": "", "median": "10000"}
    kw[column] = value
    return tsv(**kw)


def rows_of(r):
    return {x["account"]: x for x in json.loads(r.stdout)["reels"]}


class CountsAreRead(unittest.TestCase):
    def test_every_column_reads_every_count(self):
        self.assertEqual(set(sw.COUNT_COLUMNS), {"views", "followers", "median"})
        for lang, cases in READ.items():
            for column in sw.COUNT_COLUMNS:
                for text, want in cases:
                    with self.subTest(lang=lang, column=column, cell=text):
                        r = run_tool("swipe", "-", "--json", "--lang", lang, stdin=cell(column, text))
                        self.assertEqual(r.returncode, 0, r.stderr)
                        self.assertEqual(rows_of(r)["@a"][column], want)

    def test_the_multiple_is_the_real_one(self):
        r = run_tool("swipe", "-", "--json", stdin=tsv(views="1.2M", median="300K"))
        self.assertEqual(rows_of(r)["@a"]["outlier"], 4.0)
        r = run_tool("swipe", "-", "--json", "--lang", "pt-BR",
                     stdin=tsv(views="1,2 mi", median="10 mil"))
        self.assertEqual(rows_of(r)["@a"]["outlier"], 120.0)

    def test_an_empty_optional_cell_is_no_number(self):
        r = run_tool("swipe", "-", "--json", stdin=tsv(followers=""))
        self.assertIsNone(rows_of(r)["@a"]["followers"])


class ABadCountStops(unittest.TestCase):
    def test_every_column_refuses_every_bad_cell(self):
        for lang, cases in REFUSED.items():
            for column in sw.COUNT_COLUMNS:
                for text in cases:
                    with self.subTest(lang=lang, column=column, cell=text):
                        r = run_tool("swipe", "-", "--json", "--lang", lang, stdin=cell(column, text))
                        self.assertEqual(r.returncode, 2, r.stdout)
                        self.assertEqual(r.stdout, "")
                        self.assertIn(text, r.stderr)
                        self.assertIn(column, r.stderr)
                        self.assertIn("2", r.stderr)          # the line it is on
                        self.assertNotIn("Traceback", r.stderr)

    def test_nothing_is_written_to_the_swipe_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "swipe.md")
            r = run_tool("swipe", "-", "--out", out, stdin=cell("views", "1e5"))
            self.assertEqual(r.returncode, 2)
            self.assertFalse(os.path.exists(out))

    def test_igtools_raises(self):
        import sys
        sys.path.insert(0, os.path.dirname(SKILLS))
        try:
            import igtools
            with self.assertRaises(igtools.Error):
                igtools.rank_swipe(cell("median", "1e5"))
        finally:
            sys.path.remove(os.path.dirname(SKILLS))


class OneReadingOfACount(unittest.TestCase):
    def test_no_digit_stripping_outside_parse_count(self):
        with open(TOOLS["swipe"], encoding="utf-8") as fh:
            src = fh.read()
        body = re.sub(r"\ndef parse_count\(.*?(?=\n\S)", "\n", src, flags=re.S)
        self.assertIn("def parse_count(", src)
        self.assertNotRegex(body, r"\[\^\\d\]|\\D", "a count read by stripping non-digits")

    def test_units_live_in_each_language_file(self):
        for lang in READ:
            with open(os.path.join(SKILLS, "ig-viral", "lang", f"{lang}.json"), encoding="utf-8") as fh:
                units = json.load(fh)["swipe"]["units"]
            self.assertTrue(units)
            self.assertTrue(all(isinstance(v, int) and v > 1 for v in units.values()))


if __name__ == "__main__":
    unittest.main()
