"""caption.py: the README example (2 WARN), every check's branches, and the
exit-code contract (exit 0 only on READY)."""

import unittest

from _support import fixture, load, read_fixture, run_json, run_tool

cp = load("caption")
KEYWORDS = "client contracts,freelance pricing"


def statuses(a):
    return {c["check"]: c["status"] for c in a["checks"]}


def details(a):
    return {c["check"]: c["detail"] for c in a["checks"]}


class GoldenReadme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = cp.analyse(read_fixture("caption.txt"), keywords=KEYWORDS.split(","))

    def test_counts(self):
        self.assertEqual(self.a["characters"], 389)
        self.assertEqual(self.a["first_line_chars"], 133)
        self.assertTrue(self.a["truncated"])

    def test_the_two_warns(self):
        s = statuses(self.a)
        self.assertEqual(sorted(k for k, v in s.items() if v == "WARN"),
                         ["FIRST LINE", "SEARCH TERMS"])
        self.assertNotIn("FAIL", s.values())
        self.assertEqual(self.a["verdict"], "REVIEW")

    def test_details_match_the_readme(self):
        d = details(self.a)
        self.assertEqual(d["LENGTH"], "389 / 2200 characters")
        self.assertTrue(d["FIRST LINE"].startswith("133 characters, so it gets cut at 125 mid-thought"))
        self.assertEqual(d["HOOK IS CONCRETE"], "2 number(s) or name(s) in the visible window")
        self.assertEqual(d["HASHTAGS"], "3 tag(s): #freelance #contracts #agencyowner")
        self.assertEqual(d["ONE ASK"], "one call to action: comment a keyword")
        self.assertIn("1/2 present", d["SEARCH TERMS"])
        self.assertIn("Missing: client contracts", d["SEARCH TERMS"])

    def test_visible_window_is_cut_mid_word(self):
        self.assertEqual(len(self.a["visible"]), 125)
        self.assertTrue(self.a["visible"].endswith("before I si"))

    def test_box_render(self):
        out = run_tool("caption", fixture("caption.txt"), "--keywords", KEYWORDS).stdout
        self.assertIn("| I lost $18,000 because of one missing clause in a    |", out)
        self.assertIn("| thing twice before I si                              |", out)
        self.assertIn("... more +", out)
        self.assertIn("VERDICT  REVIEW", out)


class Checks(unittest.TestCase):
    def a(self, text, **kw):
        return cp.analyse(text, **kw)

    def test_ready(self):
        a = self.a("I lost $18,000 on one contract.\n\n"
                   "The clause said payment on approval, and approval never came. "
                   "Now it says delivery.\n\nComment CLAUSE for the wording.\n\n#freelance")
        self.assertEqual(a["verdict"], "READY", statuses(a))

    def test_over_limit_fails(self):
        a = self.a("I lost $5. " + "x" * 2300)
        self.assertEqual(statuses(a)["LENGTH"], "FAIL")
        self.assertEqual(a["verdict"], "FIX")

    def test_first_line_hashtag_or_mention_fails(self):
        self.assertEqual(statuses(self.a("#tag first\nthen text"))["FIRST LINE"], "FAIL")
        self.assertEqual(statuses(self.a("@someone first"))["FIRST LINE"], "FAIL")

    def test_hashtag_cap_is_five(self):
        self.assertEqual(cp.HASHTAG_LIMIT, 5)
        five = "I lost $5.\n\n" + " ".join(f"#t{i}" for i in range(5))
        six = "I lost $5.\n\n" + " ".join(f"#t{i}" for i in range(6))
        self.assertEqual(statuses(self.a(five))["HASHTAGS"], "PASS")
        self.assertEqual(statuses(self.a(six))["HASHTAGS"], "FAIL")

    def test_filler_tags_warn(self):
        a = self.a("I lost $5.\n\n#freelance #fyp #viral")
        self.assertEqual(statuses(a)["HASHTAGS"], "WARN")
        self.assertIn("#fyp", details(a)["HASHTAGS"])

    def test_tag_inside_window_warns(self):
        a = self.a("I lost $5 #freelance and here is why")
        self.assertEqual(statuses(a)["TAG PLACEMENT"], "WARN")

    def test_links_warn(self):
        self.assertEqual(statuses(self.a("I lost $5. See https://x.io/a"))["LINKS"], "WARN")
        self.assertEqual(statuses(self.a("I lost $5. See site.com/a"))["LINKS"], "WARN")

    def test_asks(self):
        self.assertEqual(statuses(self.a("I lost $5."))["ONE ASK"], "WARN")
        two = self.a("I lost $5. Save this and DM me.")
        self.assertEqual(statuses(two)["ONE ASK"], "WARN")
        self.assertIn("2 asks", details(two)["ONE ASK"])

    def test_emoji_density(self):
        self.assertEqual(statuses(self.a("I lost $5 🔥🔥🔥🔥"))["EMOJI"], "WARN")

    def test_emoji_counted_as_the_reader_sees_them(self):
        # One heart with its selector is one emoji, a flag is one, an arrow
        # in a sentence is typography (EMOJI_CASES in test_invariants).
        self.assertEqual(self.a("Done ❤️ 🇧🇷 👍🏽")["emoji"], 3)
        self.assertEqual(self.a("Before → after")["emoji"], 0)

    def test_search_terms_all_missing_fails(self):
        a = self.a("I lost $5.", keywords=["proposal software"])
        self.assertEqual(statuses(a)["SEARCH TERMS"], "FAIL")

    def test_no_keywords_no_check(self):
        self.assertNotIn("SEARCH TERMS", statuses(self.a("I lost $5.")))

    def test_truncate_flag(self):
        a = cp.analyse("a" * 100, cut=80)
        self.assertTrue(a["truncated"])
        self.assertEqual(len(a["visible"]), 80)


class Contract(unittest.TestCase):
    def test_review_exits_1(self):
        self.assertEqual(run_tool("caption", fixture("caption.txt"), "--keywords", KEYWORDS)
                         .returncode, 1)

    def test_ready_exits_0(self):
        proc = run_tool("caption", "-", stdin="I lost $5 on one contract.\n\nComment CLAUSE.\n")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_json_keeps_exit_code(self):
        proc, data = run_json("caption", fixture("caption.txt"), "--keywords", KEYWORDS)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["verdict"], "REVIEW")

    def test_stdin_equals_file(self):
        a = run_tool("caption", fixture("caption.txt")).stdout
        b = run_tool("caption", "-", stdin=read_fixture("caption.txt")).stdout
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
