"""The frontmatter description of each SKILL.md is the trigger text Claude reads
to decide whether to load the skill. It holds triggers only, in English and in
Portuguese, in one description: "Use when ..." then "Use quando ...". No summary
of the workflow (the model would follow the summary instead of the body), and no
numbers (a count in a trigger goes stale without anything noticing)."""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_FILES = sorted(glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")))
LIMIT = 1024  # the skill loader's cap on a description
EN, PT = "Use when ", "Use quando "
QUOTED = re.compile(r'"[^"\n]+"')


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def description(front):
    """The description value, unfolded: a `>-` block is its indented lines
    joined by single spaces; a one-line value is taken as written."""
    m = re.search(r"^description:[ \t]*(.*)$", front, re.M)
    if not m:
        return None
    head = m.group(1).strip()
    if head not in (">-", ">", "|", "|-"):
        return head
    lines = []
    for line in front[m.end():].split("\n")[1:]:
        if line and not line.startswith((" ", "\t")):
            break
        lines.append(line.strip())
    return " ".join(x for x in lines if x)


def check(desc):
    """Every rule the description breaks, as short strings (empty = fine)."""
    bad = []
    if not desc:
        return ["empty"]
    if len(desc) > LIMIT:
        bad.append(f"{len(desc)} chars > {LIMIT}")
    if not desc.startswith(EN):
        bad.append("does not open with 'Use when'")
    if desc.count(EN) != 1 or desc.count(PT) != 1:
        bad.append("needs exactly one 'Use when' and one 'Use quando'")
    elif desc.index(EN) > desc.index(PT):
        bad.append("English before Portuguese")
    else:
        en, pt = desc.split(PT, 1)
        if not QUOTED.search(en) or not QUOTED.search(pt):
            bad.append("each language quotes at least one thing the user says")
    if re.search(r"\d", desc):
        bad.append("holds a number")
    return bad


class Descriptions(unittest.TestCase):
    def test_found_every_skill(self):
        self.assertEqual(len(SKILL_FILES), len(os.listdir(os.path.join(ROOT, "skills"))))

    def test_every_description(self):
        for path in SKILL_FILES:
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                with open(path, encoding="utf-8") as fh:
                    front = frontmatter(fh.read())
                self.assertIsNotNone(front, "frontmatter")
                self.assertEqual(check(description(front)), [])

    def test_descriptions_differ(self):
        seen = {}
        for path in SKILL_FILES:
            with open(path, encoding="utf-8") as fh:
                seen.setdefault(description(frontmatter(fh.read())), []).append(path)
        self.assertEqual([p for p in seen.values() if len(p) > 1], [])


class TheCheckCatches(unittest.TestCase):
    """Each rule fires on a description built to break it."""

    GOOD = 'Use when the user says "plan my week". Use quando o usuário diz "planeja minha semana".'

    def test_good_passes(self):
        self.assertEqual(check(self.GOOD), [])

    def test_each_rule(self):
        cases = {
            "summary first": "Builds the week. " + self.GOOD,
            "no pt": 'Use when the user says "plan my week".',
            "pt first": 'Use quando "x". Use when "y".',
            "unquoted pt": 'Use when "plan my week". Use quando o usuário pede.',
            "number": self.GOOD.replace("week", "week off 26 formulas"),
            "too long": self.GOOD + " x" * LIMIT,
            "twice": self.GOOD + " " + self.GOOD,
        }
        for name, desc in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(check(desc), [])

    def test_folded_block_unfolds(self):
        front = 'name: x\ndescription: >-\n  Use when "a"\n  b. Use quando "c".\nother: y'
        self.assertEqual(description(front), 'Use when "a" b. Use quando "c".')


if __name__ == "__main__":
    unittest.main()
