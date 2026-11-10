"""The "Before you write" block every SKILL.md shares (fase 3, passo 3b).

A skill folder must work alone, so the steps every skill starts with are
copied into each SKILL.md between `<!-- shared:before-you-write -->` markers,
and the copies must be byte-equal. The class ("a SKILL.md") is read from
`skills/ig-*/SKILL.md`, never listed by hand. What the block has to say:
read voice.md and its **Language:** line, answer in that language, what
`{language}` and `{skill_dir}` mean. It comes before any other `##` section,
so a skill's own steps come after the shared ones.

The scripts are run from the skill's base directory, never the cwd: every
command a SKILL.md documents (found by `test_skill_lang.commands`) is written
`python3 {skill_dir}/name.py`.

Any other `<!-- shared:NAME -->` block is held to the same rules: markers
paired, every copy of a name equal (`test_templates` also compares the
log-schema copies to `templates/log.md`).
"""

import glob
import os
import re
import unittest

from _support import SKILLS
from test_skill_lang import commands, langs, scripts_by_skill

NAME = "before-you-write"
OPEN = re.compile(r"<!-- shared:([\w-]+) -->")
CLOSE = re.compile(r"<!-- /shared:([\w-]+) -->")
PREFIX = "python3 {skill_dir}/"


def skill_files():
    return sorted(glob.glob(os.path.join(SKILLS, "ig-*", "SKILL.md")))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def blocks(text):
    """{name: [body, ...]} of every shared block, in order."""
    out = {}
    for m in OPEN.finditer(text):
        end = text.find("<!-- /shared:%s -->" % m.group(1), m.end())
        if end != -1:
            out.setdefault(m.group(1), []).append(text[m.end():end])
    return out


def unprefixed(text, scripts):
    """Commands (as test_skill_lang finds them) not written `python3 {skill_dir}/x.py`."""
    names = "|".join(re.escape(s) for s in scripts)
    bad = []
    for m in re.finditer(r"\b(" + names + r")\.py\b([^`\n#]*)", text):
        if not m.group(2).strip():
            continue  # a bare mention is prose, not a command
        if text[max(0, m.start() - len(PREFIX)):m.start()] != PREFIX:
            line = text[text.rfind("\n", 0, m.start()) + 1:text.find("\n", m.start())]
            bad.append(line.strip())
    return bad


class DetectorWorks(unittest.TestCase):
    def test_planted(self):
        text = ("<!-- shared:x -->\nA\n<!-- /shared:x -->\n"
                "```bash\npython3 {skill_dir}/caption.py a.txt --lang {language}\n"
                "python3 caption.py b.txt --lang {language}\n```\n"
                "Then `caption.py c.txt`. `caption.py` counts.\n")
        self.assertEqual(blocks(text), {"x": ["\nA\n"]})
        self.assertEqual(unprefixed(text, ["caption"]),
                         ["python3 caption.py b.txt --lang {language}",
                          "Then `caption.py c.txt`. `caption.py` counts."])
        # the same commands test_skill_lang finds, so the two nets agree
        self.assertEqual(len(commands(text, ["caption"])), 3)


class EverySkillSharesTheBlock(unittest.TestCase):
    def test_one_block_per_skill(self):
        paths = skill_files()
        self.assertGreaterEqual(len(paths), 1)
        for path in paths:
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                self.assertEqual(len(blocks(read(path)).get(NAME, [])), 1)

    def test_copies_are_byte_equal(self):
        seen = {}
        for path in skill_files():
            for body in blocks(read(path)).get(NAME, []):
                seen.setdefault(body, []).append(os.path.basename(os.path.dirname(path)))
        self.assertEqual(len(seen), 1, {k[:80]: v for k, v in seen.items()})

    def test_block_says_what_it_must(self):
        bodies = {b for p in skill_files() for b in blocks(read(p)).get(NAME, [])}
        self.assertEqual(len(bodies), 1)
        body = bodies.pop()
        for needle in ("## Before you write", "~/.claude/instagram/voice.md",
                       "**Language:**", "{language}", "{skill_dir}", PREFIX, "exit 2"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)
        for v in langs():
            self.assertIn("`" + v + "`", body)
        # missing voice.md or Language line: scripts run as en
        self.assertRegex(body, r"no (Language )?line[^.]*`en`")
        # a new voice.md asks the language and writes the line the way
        # ig-setup does, and only after the user's yes
        self.assertIn("- **Language:** pt-BR", body)
        self.assertRegex(body, r"language\s+they\s+post\s+in")
        self.assertRegex(body, r"voice\.md`? only after[^.]*\byes\b")
        # numbers under the user's name come from them, never from the model
        for needle in ("**Never fabricate.**", "{{your number}}", "**Proof I can use**", "**Provas que posso usar**"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_proof_sections_named_in_the_block_exist(self):
        """The block names the proof section of each voice form by its heading."""
        body = blocks(read(skill_files()[0]))[NAME][0]
        forms = glob.glob(os.path.join(SKILLS, "..", "templates", "voice.*.md"))
        self.assertGreaterEqual(len(forms), 2)
        for form in forms:
            heads = re.findall(r"^## (.+?)\s*$", read(form), re.M)
            with self.subTest(form=os.path.basename(form)):
                self.assertTrue([h for h in heads if "**" + h + "**" in body], heads)

    def test_fabrication_rule_lives_only_in_the_block(self):
        """The rule is shared; a local copy would drift from it."""
        for path in skill_files():
            text = read(path)
            outside = OPEN.sub("", text)
            for body in blocks(text).get(NAME, []):
                outside = outside.replace(body, "")
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                self.assertNotIn("**Never fabricate.**", outside)

    def test_block_comes_before_the_skill_own_sections(self):
        for path in skill_files():
            text = read(path)
            m = OPEN.search(text)
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                self.assertTrue(m)
                before = text[:m.start()]
                self.assertEqual(re.findall(r"^## .*", before, re.M), [])
                self.assertEqual(text.count("## Before you write"), 1)


class SharedMarkersAreSound(unittest.TestCase):
    def test_markers_pair_up_and_copies_agree(self):
        copies = {}
        for path in skill_files():
            text = read(path)
            skill = os.path.basename(os.path.dirname(path))
            with self.subTest(skill=skill):
                self.assertEqual(OPEN.findall(text), CLOSE.findall(text))
            for name, bodies in blocks(text).items():
                for body in bodies:
                    copies.setdefault(name, set()).add(body)
        for name, bodies in copies.items():
            with self.subTest(block=name):
                self.assertEqual(len(bodies), 1)


class ScriptsRunFromTheSkillFolder(unittest.TestCase):
    def test_every_command_names_the_skill_dir(self):
        for d, scripts in scripts_by_skill().items():
            path = os.path.join(d, "SKILL.md")
            with self.subTest(skill=os.path.basename(d)):
                self.assertEqual(unprefixed(read(path), scripts), [])

    def test_no_skill_says_run_from_here(self):
        """Nothing tells the model to cd into the folder instead."""
        for path in skill_files():
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                self.assertNotRegex(read(path), r"\bcd (into|to) |`cd ")


if __name__ == "__main__":
    unittest.main()
