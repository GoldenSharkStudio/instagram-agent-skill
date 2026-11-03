"""The templates and the copies the skills carry of them (fase 3, passo 3a).

`templates/voice.en.md` and `templates/voice.pt-BR.md` are the same form in
two languages: same sections, same fields, the same `**Language:**` label (it
is what every skill reads, so it is a contract and does not translate), and
both offer exactly the `LANGS` of the scripts.

`templates/log.md` defines the line every skill appends to and reads from
`~/.claude/instagram/log.md`. A skill folder must work alone, so the schema is
copied into each SKILL.md that names `log.md`, between the same markers as in
the template, and every copy must be byte-equal to the template's. The class
("a SKILL.md that uses the log") is read from the files, never listed by hand.
"""

import glob
import os
import re
import subprocess
import unittest

from _support import ROOT, SKILLS
from test_skill_lang import langs

VOICES = {"en": "voice.en.md", "pt-BR": "voice.pt-BR.md"}
LOG_BLOCK = re.compile(r"<!-- shared:log-schema -->\n(.*?)<!-- /shared:log-schema -->", re.S)
FIELD = re.compile(r"^\s*(?:-|\d+\.)\s+\*\*([^*]+):\*\*", re.M)


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def skeleton(text):
    """Heading levels and the number of `**field:**` lines under each one."""
    out = []
    for block in re.split(r"^(?=#{1,6} )", text, flags=re.M):
        m = re.match(r"(#{1,6}) ", block)
        out.append((len(m.group(1)) if m else 0, len(FIELD.findall(block))))
    return out


def skills_using_log():
    out = []
    for path in sorted(glob.glob(os.path.join(SKILLS, "ig-*", "SKILL.md"))):
        with open(path, encoding="utf-8") as fh:
            if "log.md" in fh.read():
                out.append(path)
    return out


class VoiceTemplates(unittest.TestCase):
    def test_both_languages_ship(self):
        for name in VOICES.values():
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "templates", name)), name)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "templates", "voice.md")))

    def test_same_skeleton(self):
        en, pt = (skeleton(read("templates", VOICES[k])) for k in ("en", "pt-BR"))
        self.assertGreater(sum(n for _, n in en), 20)  # the parse reached the fields
        self.assertEqual(en, pt)

    def test_language_label_and_options(self):
        for lang, name in VOICES.items():
            text = read("templates", name)
            with self.subTest(template=name):
                m = re.search(r"^- \*\*Language:\*\* \(([^.)]*)\.", text, re.M)
                self.assertTrue(m, "no **Language:** line")
                self.assertEqual(sorted(re.findall(r"`([^`]+)`", m.group(1))), sorted(langs()))
                self.assertIn("`%s`" % lang, m.group(1))

    def test_pt_br_is_translated(self):
        """Every field label but Language is in Portuguese: no label is shared."""
        en, pt = (set(FIELD.findall(read("templates", VOICES[k]))) for k in ("en", "pt-BR"))
        self.assertEqual(en & pt, {"Language"})

    def test_no_reference_to_the_old_name(self):
        r = subprocess.run(["git", "grep", "-n", "templates/voice.md", "--", ".", ":!tests/test_templates.py"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)  # 1 = searched, no match; 128 = no repo


class LogSchema(unittest.TestCase):
    def template_block(self):
        blocks = LOG_BLOCK.findall(read("templates", "log.md"))
        self.assertEqual(len(blocks), 1)
        return blocks[0]

    def test_template_defines_one_line_shape(self):
        block = self.template_block()
        lines = re.findall(r"^- YYYY-MM-DD \|.*$", block, re.M)
        self.assertEqual(lines, ["- YYYY-MM-DD | type | formula | first line | account"])
        for field in ("type", "formula", "first line", "account"):
            self.assertIn("`%s`" % field, block)

    def test_class_is_read_from_the_files(self):
        names = [os.path.basename(os.path.dirname(p)) for p in skills_using_log()]
        self.assertEqual(names, ["ig-audit", "ig-comment", "ig-plan", "ig-reel"])

    def test_every_skill_carries_the_same_schema(self):
        want = self.template_block()
        for path in skills_using_log():
            with self.subTest(skill=os.path.basename(os.path.dirname(path))):
                with open(path, encoding="utf-8") as fh:
                    got = LOG_BLOCK.findall(fh.read())
                self.assertEqual(got, [want])

    def test_the_net_sees_a_drifted_copy(self):
        want = self.template_block()
        drifted = "<!-- shared:log-schema -->\n" + want.replace("account", "handle") \
            + "<!-- /shared:log-schema -->"
        self.assertNotEqual(LOG_BLOCK.findall(drifted), [want])


if __name__ == "__main__":
    unittest.main()
