"""Every write to the user's state folder waits for the user's yes.

`~/.claude/instagram/` holds the user's own files (voice.md, swipe.md,
log.md, plan.md). A skill that writes there on its own replaces work the
user may have edited by hand. So every paragraph of a SKILL.md that writes
there (a write verb next to the folder, or a command with `--out` into it)
must make the write wait for approval in that same paragraph, or, for a
command block, in the paragraph just before it.

The writes are found from the text of every `skills/ig-*/SKILL.md`, never
listed by hand, and the count is checked so a finder that sees nothing
cannot pass.
"""

import glob
import os
import re
import unittest

from _support import SKILLS

STATE = r"(?:~/\.claude/instagram/|\b(?:voice|swipe|log|plan)\.md\b)"
WRITE = re.compile(r"\b(?:write|writes|written|append|save|saves|overwrite|create|keep)\b"
                   r"[^.]{0,120}?" + STATE, re.IGNORECASE)
OUT = re.compile(r"--out\s+~/\.claude/instagram/")
# What makes a write wait: the user's yes, their approval, or their own word
# that they posted it.
GATE = re.compile(r"\byes\b|\bapprov|\bsays which\b|\bafter they\b", re.IGNORECASE)
# A paragraph that only says another skill writes the file is not a write here.
OTHER = re.compile(r"`/ig-[\w-]+` writes")


def paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def writes(text):
    """[(paragraph, gate_text)] for every paragraph that writes state."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)   # trigger text, not steps
    paras = paragraphs(text)
    out = []
    for i, p in enumerate(paras):
        is_code = p.lstrip().startswith("```")
        if is_code and OUT.search(p):
            out.append((p, paras[i - 1] if i else ""))
        elif not is_code and WRITE.search(p) and not OTHER.search(p):
            out.append((p, p))
    return out


def ungated(text):
    return [p.strip()[:100] for p, gate in writes(text) if not GATE.search(gate)]


class FinderWorks(unittest.TestCase):
    def test_planted(self):
        text = ("Write the plan to `~/.claude/instagram/plan.md`.\n\n"
                "Show it. Write `swipe.md` only after a yes.\n\n"
                "Run it:\n\n```bash\npython3 x.py --out ~/.claude/instagram/swipe.md\n```\n\n"
                "If `~/.claude/instagram/swipe.md` exists, read it. `/ig-viral` writes that file.\n")
        self.assertEqual(len(writes(text)), 3)
        self.assertEqual(len(ungated(text)), 2)


class EveryStateWriteWaitsForYes(unittest.TestCase):
    def test_writes_are_found(self):
        n = sum(len(writes(open_(p))) for p in skill_files())
        # voice.md in the shared block (14), log.md in reel/carousel/story/
        # comment, swipe.md in viral, plan.md in plan, voice.md in setup.
        self.assertGreaterEqual(n, 14 + 7)

    def test_every_write_is_gated(self):
        for path in skill_files():
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                self.assertEqual(ungated(open_(path)), [])


def skill_files():
    return sorted(glob.glob(os.path.join(SKILLS, "ig-*", "SKILL.md")))


def open_(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    unittest.main()
