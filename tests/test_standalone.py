"""Users install by copying one skill folder into ~/.claude/skills/. Each
folder that ships a tool must run from a copy that has nothing beside it.
(ig-viral, the one folder that reaches into a sibling, is covered in
test_swipe.Standalone.)"""

import os
import shutil
import tempfile
import unittest

from _support import SKILLS, fixture, run_tool

CASES = [
    ("ig-reel", "hookscore.py", [fixture("hooks.txt")], 0),
    ("ig-reel", "beats.py", [fixture("script.txt"), "--target", "30"], 0),
    ("ig-caption", "caption.py", [fixture("caption.txt")], 1),
    ("ig-human", "humanize.py", [fixture("bad_draft.txt"), "--report"], 0),
    ("ig-human", "detect.py", [fixture("good_draft.txt")], 0),
]


class CopiedAlone(unittest.TestCase):
    def test_each_tool_runs_from_a_lone_copy(self):
        for folder, script, args, code in CASES:
            with self.subTest(tool=script), tempfile.TemporaryDirectory() as d:
                dest = os.path.join(d, folder)
                shutil.copytree(os.path.join(SKILLS, folder), dest)
                proc = run_tool(os.path.join(dest, script), *args, cwd=d)
                self.assertEqual(proc.returncode, code, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertTrue(proc.stdout.strip())

    def test_runs_from_any_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            proc = run_tool("detect", fixture("good_draft.txt"), cwd=d)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
