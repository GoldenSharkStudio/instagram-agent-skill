"""Every skill that writes text for Instagram ends at the user's yes.

The README promises that nothing posts: every skill ends with a copy-ready
block and an explicit approval. So every `skills/ig-*/SKILL.md` must say, in
the same words, that nothing goes out until the user says yes, except the
skills that write nothing to publish, each declared below with its reason.
The class is read from the folder, so a new skill is held to the gate unless
someone writes down why it is not.
"""

import glob
import os
import re
import unittest

from _support import SKILLS

GATE = re.compile(r"[Nn]othing\s+is\s+(?:posted|sent|saved)[^.]*?\buntil\s+the\s+user\s+says\s+yes\b")

# Skills whose output is not text for Instagram, each with its reason.
# Checked: each must exist.
NOT_PUBLISHING = {
    "ig-audit": "a report on what was posted, nothing to post",
    "ig-plan": "a week plan; each post is drafted by another skill, which has the gate",
    "ig-setup": "writes voice.md, gated on its own yes",
    "ig-viral": "research into swipe.md, gated on its own yes",
}


def skills():
    return {os.path.basename(os.path.dirname(p)): p
            for p in sorted(glob.glob(os.path.join(SKILLS, "ig-*", "SKILL.md")))}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class GateFinder(unittest.TestCase):
    def test_planted(self):
        self.assertTrue(GATE.search("Nothing is posted until the user\nsays yes. They paste it."))
        self.assertTrue(GATE.search("Then the gate: nothing is sent until the user says yes."))
        self.assertFalse(GATE.search("Nothing is posted. The user pastes it."))


class EveryPublishingSkillHasTheGate(unittest.TestCase):
    def test_exemptions_exist(self):
        self.assertLessEqual(set(NOT_PUBLISHING), set(skills()))

    def test_gate(self):
        found = skills()
        self.assertGreaterEqual(len(found), 14)
        for name, path in found.items():
            if name in NOT_PUBLISHING:
                continue
            with self.subTest(skill=name):
                self.assertRegex(read(path), GATE)


if __name__ == "__main__":
    unittest.main()
