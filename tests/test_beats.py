"""beats.py: golden values from the README beat sheet, plus each flag."""

import unittest

from _support import fixture, load, read_fixture, run_json, run_tool

bt = load("beats")


class GoldenReadme(unittest.TestCase):
    """The README "BEAT SHEET" block: 73 words, ~26.6s, beat 2 flagged."""

    @classmethod
    def setUpClass(cls):
        cls.a = bt.analyse(read_fixture("script.txt"), wpm=165, target=30)

    def test_totals(self):
        self.assertEqual(self.a["total_words"], 73)
        self.assertEqual(round(self.a["total_seconds"], 1), 26.6)

    def test_timecodes_and_durations(self):
        starts = [bt.tc(r["start"]) for r in self.a["beats"]]
        durs = [round(r["dur"], 1) for r in self.a["beats"]]
        self.assertEqual(starts, ["0:00.0", "0:02.9", "0:17.4", "0:20.4", "0:23.3"])
        self.assertEqual(durs, [2.9, 14.6, 2.9, 2.9, 3.3])

    def test_labels(self):
        self.assertEqual([r["label"] for r in self.a["beats"]], ["HOOK", "MID", "", "", "CTA"])

    def test_long_beat_flagged(self):
        self.assertEqual(self.a["beats"][1]["flags"], ["14.6s on one beat"])
        self.assertTrue(any(n.startswith("Beat(s) 2 run past 4s") for n in self.a["notes"]))

    def test_loop_and_target_notes(self):
        notes = " | ".join(self.a["notes"])
        self.assertIn('Loops: the last beat repeats "$18,000" from the hook', notes)
        self.assertIn("3.5s under target. Either add 9 words", notes)

    def test_render_header(self):
        out = run_tool("beats", fixture("script.txt"), "--target", "30").stdout
        self.assertIn("BEAT SHEET  ·  73 words  ·  ~26.6s at 165 wpm  ·  target 30.0s", out)


class Flags(unittest.TestCase):
    def test_slow_hook(self):
        a = bt.analyse("This hook takes far too many words to say before anything happens at all.\n"
                       "Then $5.")
        self.assertTrue(a["beats"][0]["flags"])
        self.assertTrue(any(n.startswith("Beat 1 takes") for n in a["notes"]))

    def test_hook_without_concrete(self):
        a = bt.analyse("this is a line\nanother line here\n")
        self.assertTrue(any("no number and no name" in n for n in a["notes"]))

    def test_abstract_run(self):
        a = bt.analyse("I lost $5.\nit hurt a lot\nit really did\nit was bad\nthe end $5\n")
        self.assertTrue(any(n.startswith("Beats 2-4 have nothing concrete") for n in a["notes"]))

    def test_no_loop(self):
        a = bt.analyse("I lost $5 today.\nThe weather was nice.\n")
        self.assertTrue(any(n.startswith("No loop.") for n in a["notes"]))

    def test_over_target_and_on_target(self):
        script = read_fixture("script.txt")
        over = bt.analyse(script, target=15)
        self.assertTrue(any("over target" in n for n in over["notes"]))
        on = bt.analyse(script, target=27)
        self.assertTrue(any(n.startswith("Length is on target") for n in on["notes"]))

    def test_wpm_scales_time(self):
        slow = bt.analyse(read_fixture("script.txt"), wpm=120)
        fast = bt.analyse(read_fixture("script.txt"), wpm=200)
        self.assertGreater(slow["total_seconds"], fast["total_seconds"])
        self.assertEqual(slow["total_words"], fast["total_words"])

    def test_long_paragraph_is_split_at_sentences(self):
        para = " ".join(["This sentence has exactly seven words here."] * 6)
        a = bt.analyse(para)
        self.assertGreater(len(a["beats"]), 1)

    def test_single_line_is_hook_and_cta(self):
        a = bt.analyse("I lost $5.")
        self.assertEqual(a["beats"][0]["label"], "HOOK/CTA")


class Contract(unittest.TestCase):
    def test_exit_0_and_json(self):
        proc, data = run_json("beats", fixture("script.txt"), "--target", "30")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(data["total_words"], 73)
        self.assertEqual(set(data), {"wpm", "target", "total_seconds", "total_words",
                                     "beats", "notes"})

    def test_empty_exits_2(self):
        proc = run_tool("beats", "-", stdin="\n  \n")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("empty script", proc.stderr)

    def test_stdin_equals_file(self):
        a = run_tool("beats", fixture("script.txt")).stdout
        b = run_tool("beats", "-", stdin=read_fixture("script.txt")).stdout
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
