"""hookscore.py: golden values from the README ranking, the checks, the
dealbreakers, and the exit-code contract that skills read as a verdict."""

import json
import unittest

from _support import fixture, load, read_fixture, run_json, run_tool

hs = load("hookscore")

# The README "HOOK RANKING" block. Score, verdict, weakest check (and its
# score) and the dealbreakers each hook trips.
GOLDEN = [
    ("Nobody tells you that your first 30 reels are supposed to flop.",
     85.6, "STRONG", "SPECIFICITY", 75, []),
    ("I lost $18,000 because of one missing contract.",
     81.4, "STRONG", "ADDRESS", 70, []),
    ("Stop scrolling if you want to grow on Instagram in 2026 🔥",
     54.4, "OK", "STAKES", 70, ["stop scrolling", "Emoji"]),
    ("Hey guys, today I wanted to talk about content strategy",
     9.6, "WEAK", "FRONTLOAD", 0, ["Greeting"]),
]


class GoldenReadme(unittest.TestCase):
    def test_fixture_is_the_readme_batch(self):
        lines = [l for l in read_fixture("hooks.txt").splitlines() if l.strip()]
        self.assertEqual(lines, [g[0] for g in GOLDEN])

    def test_each_hook_matches_the_readme(self):
        for hook, score, verdict, weakest, wscore, flags in GOLDEN:
            with self.subTest(hook=hook):
                results, overall, got_verdict, got_flags = hs.run(hook)
                self.assertEqual(round(overall, 1), score)
                self.assertEqual(got_verdict, verdict)
                got_weakest = min(hs.CHECKS, key=lambda c: results[c][0])
                self.assertEqual(got_weakest, weakest)
                self.assertEqual(round(results[weakest][0]), wscore)
                self.assertEqual(len(got_flags), len(flags))
                for needle, msg in zip(flags, got_flags):
                    self.assertIn(needle, msg)

    def test_ranking_table_order_and_text(self):
        proc = run_tool("hookscore", fixture("hooks.txt"))
        out = proc.stdout
        self.assertIn("HOOK RANKING", out)
        positions = [out.index(f"{g[1]:5.1f} {g[2]:<7}") for g in GOLDEN]
        self.assertEqual(positions, sorted(positions), "ranked high to low")
        self.assertIn("->  85.6 STRONG  Nobody tells you that your first 30 reels are supposed to f...",
                      out)
        self.assertIn("weakest: FRONTLOAD (0)", out)

    def test_json_batch_shape(self):
        proc, data = run_json("hookscore", fixture("hooks.txt"))
        self.assertIsInstance(data, list)
        self.assertEqual([d["score"] for d in data], [g[1] for g in GOLDEN])
        for d in data:
            self.assertEqual(set(d), {"hook", "checks", "weakest", "flags", "score", "verdict"})
            self.assertEqual(set(d["checks"]), set(hs.CHECKS))

    def test_json_single_is_an_object(self):
        proc, data = run_json("hookscore", "--hook", GOLDEN[1][0])
        self.assertIsInstance(data, dict)
        self.assertEqual(data["score"], 81.4)


class Checks(unittest.TestCase):
    def test_length_band(self):
        self.assertEqual(hs.check_length("one two three four five")[0], 100.0)
        self.assertEqual(hs.check_length("one two")[0], 40.0)
        long = " ".join(["word"] * 20)
        self.assertLess(hs.check_length(long)[0], 30)

    def test_money_with_comma_is_one_word(self):
        self.assertEqual(len(hs.words("I lost $18,000 today")), 4)

    def test_spoken_numbers_count_as_concrete(self):
        # The fixed bug named in the README: "zero dollars" scored as abstract.
        score, detail = hs.check_specificity("I made zero dollars from three books")
        self.assertGreater(score, 15.0)
        self.assertIn("zero", detail)

    def test_one_and_first_are_not_quantities(self):
        score, _ = hs.check_specificity("the one thing everybody gets wrong")
        self.assertEqual(score, 15.0)

    def test_stakes(self):
        self.assertEqual(hs.check_stakes("a nice morning")[0], 20.0)
        self.assertEqual(hs.check_stakes("never do this")[0], 70.0)
        self.assertEqual(hs.check_stakes("never pay $5 for it")[0], 100.0)

    def test_frontload_weak_opener_penalty(self):
        strong, _ = hs.check_frontload("Never sign a contract like this")
        weak, detail = hs.check_frontload("So basically never sign this")
        self.assertGreater(strong, weak)
        self.assertIn("weak opener", detail)

    def test_address_ladder(self):
        self.assertEqual(hs.check_address("you are doing it wrong")[0], 100.0)
        self.assertEqual(hs.check_address("Steal this contract clause")[0], 90.0)
        self.assertEqual(hs.check_address("I lost the deal")[0], 70.0)
        self.assertEqual(hs.check_address("The market moved")[0], 35.0)

    def test_every_dealbreaker_fires(self):
        cases = [
            "Stop scrolling, this matters",
            "In this video I explain contracts",
            "Hey there, contracts matter",  # "Hey," with a comma is a known gap (A Fazer)
            "Contracts matter #freelance",
            "Contracts matter 🔥",
        ]
        for text, (pattern, _) in zip(cases, hs.DEALBREAKERS):
            with self.subTest(text=text):
                self.assertTrue(pattern.search(text))

    def test_dealbreaker_blocks_strong(self):
        _, _, verdict, flags = hs.run("Stop scrolling: you lost $18,000 on one contract")
        self.assertTrue(flags)
        self.assertNotEqual(verdict, "STRONG")

    def test_run_signature_is_what_swipe_imports(self):
        out = hs.run("I lost $18,000 because of one missing contract.")
        self.assertEqual(len(out), 4)
        results, overall, verdict, flags = out
        self.assertIsInstance(overall, float)
        self.assertIn(verdict, {"STRONG", "OK", "WEAK"})


class ExitCodes(unittest.TestCase):
    """Skills read the exit code as the verdict. Threshold: hookscore.PASS_SCORE."""

    def test_strong_batch_exits_0(self):
        self.assertEqual(run_tool("hookscore", fixture("hooks.txt")).returncode, 0)

    def test_weak_batch_exits_1(self):
        proc = run_tool("hookscore", "-", stdin="Hey guys, today I wanted to talk\n")
        self.assertEqual(proc.returncode, 1)

    def test_single_hook_exit(self):
        self.assertEqual(run_tool("hookscore", "--hook", GOLDEN[0][0]).returncode, 0)
        self.assertEqual(run_tool("hookscore", "--hook", GOLDEN[3][0]).returncode, 1)

    def test_json_keeps_the_exit_code(self):
        self.assertEqual(run_tool("hookscore", fixture("hooks.txt"), "--json").returncode, 0)
        self.assertEqual(run_tool("hookscore", "--hook", GOLDEN[3][0], "--json").returncode, 1)

    def test_empty_input_exits_2(self):
        proc = run_tool("hookscore", "-", stdin="\n\n")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("nothing to score", proc.stderr)

    def test_stdin_equals_file(self):
        a = run_tool("hookscore", fixture("hooks.txt"), "--json").stdout
        b = run_tool("hookscore", "-", "--json", stdin=read_fixture("hooks.txt")).stdout
        self.assertEqual(json.loads(a), json.loads(b))

    def test_exit_threshold_is_a_named_constant(self):
        # Pins today's behaviour (exit 1 below 70). The ranking text and
        # ig-reel/SKILL.md still say 50; aligning the two is an open decision.
        self.assertEqual(getattr(hs, "PASS_SCORE", None), 70)


if __name__ == "__main__":
    unittest.main()
