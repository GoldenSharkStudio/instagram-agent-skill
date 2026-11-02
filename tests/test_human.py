"""humanize.py and detect.py: the three cleaning passes, the five checks,
the before/after delta, and the exit-code contract."""

import json
import os
import tempfile
import unittest

from _support import fixture, load, read_fixture, run_json, run_tool

hz = load("humanize")
dt = load("detect")
LEX = hz.load_lexicon()


def clean(text):
    return hz.humanize(text, LEX)[0]


class InvisiblePass(unittest.TestCase):
    def test_zero_width_and_bom_deleted(self):
        self.assertEqual(clean("he​llo﻿ wor‍ld"), "hello world\n")

    def test_nbsp_becomes_space(self):
        self.assertEqual(clean("a b"), "a b\n")

    def test_tag_characters_deleted(self):
        self.assertEqual(clean("ok\U000E0041\U000E0042 done"), "ok done\n")

    def test_report_names_them(self):
        _, report = hz.humanize("x​y", LEX)
        self.assertEqual(report["invisible"][0]["count"], 1)


class TypographicPass(unittest.TestCase):
    def test_em_dash_to_comma(self):
        self.assertEqual(clean("I signed it — then I read it."), "I signed it, then I read it.\n")
        self.assertEqual(clean("signed—read"), "signed, read\n")

    def test_en_dash_range_and_clause(self):
        self.assertEqual(clean("5–10 reels"), "5-10 reels\n")

    def test_curly_quotes_and_ellipsis(self):
        self.assertEqual(clean("“Fine,” he said… ‘ok’"), '"Fine," he said... \'ok\'\n')

    def test_no_comma_before_punctuation(self):
        self.assertEqual(clean("I waited —."), "I waited.\n")


class LexicalPass(unittest.TestCase):
    def test_word_replaced_case_matched(self):
        self.assertEqual(clean("It is crucial."), "It is important.\n")
        self.assertEqual(clean("Crucial step."), "Important step.\n")

    def test_phrase_beats_word(self):
        # "delve into" is listed and must win over "delve".
        out = clean("We delve into contracts.")
        self.assertNotIn("delve", out.lower())
        self.assertNotIn("into into", out)

    def test_deleted_opener_restores_capital(self):
        out = clean("Stop scrolling. this changed my rate.")
        self.assertTrue(out[0].isupper(), out)

    def test_lowercase_voice_is_preserved(self):
        out = clean("stop scrolling. i only write in lower case. that is the style.")
        self.assertEqual(out, out.lower())

    def test_urls_untouched(self):
        url = "https://example.com/crucial—robust"
        self.assertIn(url, clean(f"See {url} now."))

    def test_no_orphan_punctuation_line(self):
        out = clean("Line one.\nFollow for more.\nLine three.")
        for line in out.splitlines():
            self.assertNotRegex(line, r"^\s*[,.;:!?]")

    @unittest.expectedFailure
    def test_known_bug_orphan_conjunction(self):
        # Two deleted phrases joined by "and" leave "And!" on its own line.
        # Logged in docs/PM/A Fazer.md; fix with fix-de-classe in phase 2.
        out = clean("Line one.\nFollow for more and tag someone who needs this!\n")
        self.assertNotIn("And!", out)


class Structures(unittest.TestCase):
    def test_flags_not_fixes(self):
        text = "It's not just about posting, it's about the craft."
        out, report = hz.humanize(text, LEX)
        self.assertIn("not just", out)
        self.assertTrue(any("not" in s["name"].lower() for s in report["structures"]))

    def test_uniform_sentence_length_flagged(self):
        text = "This is a short line. This is a short line. This is a short line. This is a short line."
        _, report = hz.humanize(text, LEX)
        self.assertTrue(any(s["name"].startswith("Uniform sentence length")
                            for s in report["structures"]))


class HumanizeCli(unittest.TestCase):
    def test_report_goes_to_stderr_text_to_stdout(self):
        proc = run_tool("humanize", fixture("bad_draft.txt"), "--report")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("HUMANIZE REPORT", proc.stderr)
        self.assertNotIn("HUMANIZE REPORT", proc.stdout)
        self.assertNotIn("—", proc.stdout)

    def test_out_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.txt")
            proc = run_tool("humanize", fixture("bad_draft.txt"), "-o", path)
            self.assertEqual(proc.stdout, "")
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), clean(read_fixture("bad_draft.txt")))

    def test_json_shape(self):
        proc, data = run_json("humanize", fixture("bad_draft.txt"))
        self.assertEqual(set(data), {"text", "report"})
        self.assertEqual(set(data["report"]), {"invisible", "typographic", "lexical", "structures"})

    def test_custom_lexicon(self):
        with tempfile.TemporaryDirectory() as d:
            lex = dict(LEX, words=[{"find": "contract", "replace": "deal", "family": "test"}],
                       phrases=[])
            path = os.path.join(d, "lex.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(lex, fh)
            proc = run_tool("humanize", "-", "--lexicon", path, stdin="One contract.\n")
            self.assertEqual(proc.stdout, "One deal.\n")

    def test_idempotent_on_its_own_output(self):
        once = clean(read_fixture("bad_draft.txt"))
        self.assertEqual(clean(once), once)


class Detect(unittest.TestCase):
    def test_bad_draft_flagged(self):
        results, overall, verdict = dt.run(read_fixture("bad_draft.txt"), LEX)
        self.assertEqual(verdict, "FLAGGED")
        self.assertEqual(round(overall, 1), 29.3)
        self.assertEqual(results["SLOP DENSITY"][0], 0.0)
        self.assertIn("17 stock terms", results["SLOP DENSITY"][1])
        self.assertIn("2 em dash", results["FINGERPRINT"][1])

    def test_good_draft_passes(self):
        _, overall, verdict = dt.run(read_fixture("good_draft.txt"), LEX)
        self.assertEqual(verdict, "PASS")
        self.assertGreaterEqual(overall, 70)

    def test_humanize_moves_the_score(self):
        before = dt.run(read_fixture("bad_draft.txt"), LEX)[1]
        after_results, after, verdict = dt.run(clean(read_fixture("bad_draft.txt")), LEX)
        self.assertEqual(round(after, 1), 74.1)
        self.assertEqual(verdict, "REVIEW")  # structures are flagged, not fixed
        self.assertGreater(after, before + 40)
        self.assertEqual(after_results["FINGERPRINT"][0], 100.0)

    def test_short_text_is_not_judged(self):
        results, _, _ = dt.run("Too short.", LEX)
        self.assertEqual(results["BURSTINESS"], (50.0, "too short to judge"))

    def test_invisible_chars_hit_fingerprint(self):
        text = read_fixture("good_draft.txt")
        dirty = text.replace(" ", "​ ", 5)
        self.assertLess(dt.run(dirty, LEX)[0]["FINGERPRINT"][0],
                        dt.run(text, LEX)[0]["FINGERPRINT"][0])


class DetectCli(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(run_tool("detect", fixture("bad_draft.txt")).returncode, 1)
        self.assertEqual(run_tool("detect", fixture("good_draft.txt")).returncode, 0)

    def test_json_keeps_exit_code(self):
        proc, data = run_json("detect", fixture("bad_draft.txt"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["verdict"], "FLAGGED")
        proc, _ = run_json("detect", fixture("good_draft.txt"))
        self.assertEqual(proc.returncode, 0)

    def test_compare_uses_the_last_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            after = os.path.join(d, "after.txt")
            with open(after, "w", encoding="utf-8") as fh:
                fh.write(read_fixture("good_draft.txt"))
            proc = run_tool("detect", fixture("bad_draft.txt"), after)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("29.3 FLAGGED  ->  84.2 PASS   (+54.9)", proc.stdout)
            proc, data = run_json("detect", fixture("bad_draft.txt"), after)
            self.assertIsInstance(data, list)
            self.assertEqual([p["verdict"] for p in data], ["FLAGGED", "PASS"])
            self.assertEqual(proc.returncode, 0)

    def test_stdin_equals_file(self):
        a = run_tool("detect", fixture("bad_draft.txt")).stdout
        b = run_tool("detect", "-", stdin=read_fixture("bad_draft.txt")).stdout
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
