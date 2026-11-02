"""humanize.py and detect.py: the three cleaning passes, the five checks,
the before/after delta, and the exit-code contract."""

import json
import os
import re
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

    def test_orphan_conjunction_sample(self):
        # The original report: two deleted phrases joined by "and" left "And!".
        out = clean("Line one.\nFollow for more and tag someone who needs this!\n")
        self.assertEqual(out, "Line one.\n")


def deletable_entries(lex):
    """Every lexicon entry whose replacement is empty, read from slop.en.json,
    so a new deletion joins the net below without being registered."""
    return [e["find"] for e in lex["phrases"] + lex["words"] if e["replace"] == ""]


# English coordinating conjunctions plus the two spoken joiners ("so", "then",
# "plus") that captions use the same way. This is the spec the data must meet:
# drop one from slop.en.json and the coverage guard below names it.
CONJUNCTIONS = ("and", "or", "but", "so", "plus", "yet", "nor", "then")


class OrphanConjunctionNet(unittest.TestCase):
    """Class net: deleting a lexicon entry takes the conjunction that joined it
    to the sentence along with it. Every deletable entry x every conjunction x
    the four places a conjunction sits next to a deleted chunk."""

    CASES = (
        ("Line one.\n{a} {c} {b}!\n", "Line one.\n"),
        ("We shipped it today {c} {a}.\n", "We shipped it today.\n"),
        ("We shipped it today, {c} {a}!\n", "We shipped it today!\n"),
        ("{a}, {c} {b}.\nLine two.\n", "Line two.\n"),
    )

    def test_data_covers_every_conjunction(self):
        missing = [c for c in CONJUNCTIONS if c not in LEX["conjunctions"]]
        self.assertEqual(missing, [], "slop.en.json conjunctions lost an entry")

    def test_no_conjunction_survives_a_deletion(self):
        entries = deletable_entries(LEX)
        self.assertGreater(len(entries), 0)  # the scan reached the data
        broken = []
        for i, a in enumerate(entries):
            b = entries[(i + 1) % len(entries)]
            for c in CONJUNCTIONS:
                for template, want in self.CASES:
                    text = template.format(a=a, b=b, c=c)
                    got = clean(text)
                    if got != want:
                        broken.append((text, got))
        self.assertEqual(broken[:5], [], f"{len(broken)} cases strand a conjunction")

    def test_users_own_conjunctions_are_kept(self):
        # Only a conjunction touching a deleted chunk goes. The writer's own
        # "so" and "and" at the end of a clause are not residue.
        for text in ("I think so.\n", "Salt and pepper, or so.\n",
                     "Rock and roll. Follow for more.\n", "Then what? And then?\n"):
            with self.subTest(text=text):
                self.assertEqual(clean(text), text.replace(" Follow for more.", ""))


class EveryEntryMatchesAtTheEdges(unittest.TestCase):
    """Class net: a lexicon entry is found wherever it sits, including at the
    very end of the text and right before "!", where closers live. An entry
    that starts or ends on punctuation ("what are your thoughts?") broke a
    fixed \\b there. Both compilers (humanize, detect) over every entry."""

    PLACES = ("Great post. {find}", "Great post, {find}!\n", "{find}\n")

    def entries(self):
        found = LEX["phrases"] + LEX["words"]
        self.assertGreater(len(found), 100)  # the scan reached the data
        return found

    def test_humanize_replaces_every_entry_everywhere(self):
        missed = []
        for e in self.entries():
            if e["find"].lower() in e["replace"].lower():
                continue  # a replacement that contains its own find cannot be checked this way
            for place in self.PLACES:
                if e["find"].lower() in clean(place.format(find=e["find"])).lower():
                    missed.append((e["find"], place))
        self.assertEqual(missed, [])

    def test_detect_counts_every_entry_everywhere(self):
        missed = [(e["find"], place) for e in self.entries() for place in self.PLACES
                  if dt.check_slop(place.format(find=e["find"]), LEX)[1].startswith("0 stock")]
        self.assertEqual(missed, [])


def nested_lexicon_pairs(lex):
    """(short, long) for every lexicon entry found whole-word inside another.
    Read from slop.en.json, so a new overlapping entry joins the net."""
    entries = [e["find"] for e in lex["words"] + lex["phrases"]]
    return [(a, b) for a in entries for b in entries
            if a != b and re.search(r"\b" + re.escape(a) + r"\b", b, re.IGNORECASE)]


class NestedLexiconCountsOnce(unittest.TestCase):
    """Class net: a phrase that contains another entry is one stock term,
    not two. Every member of the lexicon that counts matches is checked."""

    def test_pairs_come_from_the_lexicon(self):
        pairs = nested_lexicon_pairs(LEX)
        self.assertIn(("delve", "delve into"), pairs)
        self.assertGreaterEqual(len(pairs), 6)

    def test_detect_counts_the_long_phrase_once(self):
        for short, long in nested_lexicon_pairs(LEX):
            with self.subTest(phrase=long):
                detail = dt.check_slop(f"Today we {long} it.", LEX)[1]
                self.assertTrue(detail.startswith("1 stock terms"), detail)
                self.assertTrue(detail.endswith(f"({long})"), detail)

    def test_detect_still_counts_the_short_word_alone(self):
        for short, long in nested_lexicon_pairs(LEX):
            with self.subTest(word=short):
                self.assertTrue(dt.check_slop(f"Today we {short} it.", LEX)[1].startswith("1 stock"))

    def test_detect_counts_both_when_both_appear_apart(self):
        detail = dt.check_slop("We delve into it. Then we delve again.", LEX)[1]
        self.assertTrue(detail.startswith("2 stock terms"), detail)

    def test_humanize_replaces_the_long_phrase_once(self):
        for short, long in nested_lexicon_pairs(LEX):
            with self.subTest(phrase=long):
                hits = hz.pass_lexical(f"Today we {long} it.", LEX)[1]
                self.assertEqual([(h["find"], h["count"]) for h in hits], [(long, 1)])


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
        self.assertIn("16 stock terms", results["SLOP DENSITY"][1])
        self.assertIn("2 em dash", results["FINGERPRINT"][1])

    def test_good_draft_passes(self):
        _, overall, verdict = dt.run(read_fixture("good_draft.txt"), LEX)
        self.assertEqual(verdict, "PASS")
        self.assertGreaterEqual(overall, 70)

    def test_humanize_moves_the_score(self):
        before = dt.run(read_fixture("bad_draft.txt"), LEX)[1]
        after_results, after, verdict = dt.run(clean(read_fixture("bad_draft.txt")), LEX)
        self.assertEqual(round(after, 1), 74.4)
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


class TellsHoldThePass(unittest.TestCase):
    """Owner's rule (02/11): a structural tell is the part a script cannot
    rewrite, so while one is left the verdict stops at REVIEW, whatever the
    score. The rule reads only the tell count, so three tells of different
    shape (sentence, line prefix, tag run) stand for all of them."""

    def test_humanized_bad_draft_stops_at_review(self):
        after = clean(read_fixture("bad_draft.txt"))
        results, overall, verdict = dt.run(after, LEX)
        self.assertGreaterEqual(overall, 70)               # the score alone would pass
        self.assertGreaterEqual(min(r[0] for r in results.values()), 55)
        self.assertEqual(verdict, "REVIEW")

    def test_one_tell_of_any_kind_holds_a_passing_draft(self):
        base = read_fixture("good_draft.txt")
        self.assertEqual(dt.run(base, LEX)[2], "PASS")
        samples = {"not-just": "It's not just a tool, it's a system.",
                   "rocket": "🚀 Post daily",
                   "hashtag-wall": "#a #b #c #d #e #f #g #h"}
        ids = {s["id"] for s in LEX["structures"]}
        self.assertLessEqual(set(samples), ids, "a sample names a tell slop.en.json lost")
        for tell, sample in samples.items():
            with self.subTest(tell=tell):
                text = base + "\n" + sample + "\n"
                self.assertGreater(dt.count_tells(text, LEX)[0], 0, "sample does not trip it")
                self.assertEqual(dt.run(text, LEX)[2], "REVIEW")

    def test_render_names_the_tells_not_the_weakest_check(self):
        with tempfile.TemporaryDirectory() as d:
            after = os.path.join(d, "after.txt")
            run_tool("humanize", fixture("bad_draft.txt"), "-o", after)
            proc = run_tool("detect", after)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("structural tell(s) left", proc.stdout)
        self.assertNotIn("Weakest signal", proc.stdout)


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

    def test_json_reports_structural_tells(self):
        _, data = run_json("detect", fixture("bad_draft.txt"))
        self.assertEqual(data["structural_tells"], 13)
        _, data = run_json("detect", fixture("good_draft.txt"))
        self.assertEqual(data["structural_tells"], 0)

    def test_stdin_equals_file(self):
        a = run_tool("detect", fixture("bad_draft.txt")).stdout
        b = run_tool("detect", "-", stdin=read_fixture("bad_draft.txt")).stdout
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
