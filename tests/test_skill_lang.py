"""The SKILL.md files pass the user's language to every script (fase 2, passo 3c).

The class is "every place a SKILL.md runs a script", read from the SKILL.md
files and the scripts on disk, never listed by hand: a script is any `*.py` in
the skill folder, and a command is that script's name followed by arguments
(a bare mention like "`caption.py` counts them" is prose, not a command).
Every command must carry `--lang {language}`, the placeholder the SKILL.md
explains, and every command must still run as written: an option that does
not exist, or `--lang` with the wrong value, is a usage error (exit 2) here.

The values offered in `templates/voice.md`, the README and CLAUDE.md come from
`LANGS` in the scripts, so a language added to the code without the docs, or
the other way round, fails here.
"""

import ast
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from _support import ROOT, SKILLS, fixture

PLACEHOLDER = "{language}"
# Other placeholders the SKILL.md commands use, with a value the tool accepts.
OTHER_PLACEHOLDERS = {"length": "30"}

# Files the documented commands name, mapped to a fixture with the right shape.
FILES = {
    "hooks.txt": "hooks.txt",
    "script.txt": "script.txt",
    "caption.txt": "caption.txt",
    "draft.txt": "bad_draft.txt",
    "before.txt": "bad_draft.txt",
    "after.txt": "good_draft.txt",
    "clean.txt": "good_draft.txt",
    "captured.tsv": "captured.tsv",
}


def scripts_by_skill():
    out = {}
    for path in sorted(glob.glob(os.path.join(SKILLS, "ig-*", "*.py"))):
        out.setdefault(os.path.dirname(path), []).append(os.path.basename(path)[:-3])
    return out


def commands(text, scripts):
    """Every command line in `text` that runs one of `scripts`: (script, argv).

    A command is `name.py` followed by at least one argument, inside a code
    block line or inside backticks. Arguments run to the end of the line, the
    closing backtick or a `#` comment."""
    names = "|".join(re.escape(s) for s in scripts)
    pat = re.compile(r"(?:python3\s+)?\b(" + names + r")\.py\b([^`\n#]*)")
    found = []
    for m in pat.finditer(text):
        args = m.group(2).strip()
        if args:
            found.append((m.group(1), args))
    return found


def langs():
    """LANGS read from the source of one script (the copies are kept equal
    by test_lang_flag); every script is checked to declare the same tuple."""
    seen = set()
    for path in glob.glob(os.path.join(SKILLS, "ig-*", "*.py")):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and getattr(node.targets[0], "id", None) == "LANGS"):
                seen.add(ast.literal_eval(node.value))
    assert len(seen) == 1, seen
    return seen.pop()


def shipped(skill_dir):
    """Languages whose every data file is in this folder: each `*en.json` the
    folder ships (`lang/en.json`, `slop.en.json`) has its pair for the code."""
    en = glob.glob(os.path.join(skill_dir, "lang", "en.json")) + glob.glob(
        os.path.join(skill_dir, "slop.en.json"))
    assert en, skill_dir
    return [v for v in langs() if v != "auto"
            and all(os.path.exists(p[:-len("en.json")] + v + ".json") for p in en)]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class DetectorWorks(unittest.TestCase):
    """The extractor finds a planted command and ignores prose mentions."""

    def test_planted(self):
        text = ("```bash\npython3 caption.py caption.txt --keywords \"a,b\"   # lint\n```\n"
                "Run `caption.py` with the terms. Then `caption.py draft.txt`.\n")
        self.assertEqual(commands(text, ["caption"]),
                         [("caption", 'caption.txt --keywords "a,b"'),
                          ("caption", "draft.txt")])


class EveryCommandPassesTheLanguage(unittest.TestCase):
    def test_every_skill_with_a_script_has_commands(self):
        by_skill = scripts_by_skill()
        self.assertEqual(sorted(os.path.basename(d) for d in by_skill),
                         ["ig-caption", "ig-human", "ig-reel", "ig-viral"])
        for d, scripts in by_skill.items():
            text = read("skills", os.path.basename(d), "SKILL.md")
            used = {s for s, _ in commands(text, scripts)}
            with self.subTest(skill=os.path.basename(d)):
                self.assertEqual(used, set(scripts), "a script the SKILL.md never runs")

    def test_every_command_carries_the_placeholder(self):
        missing = []
        for d, scripts in scripts_by_skill().items():
            text = read("skills", os.path.basename(d), "SKILL.md")
            for script, args in commands(text, scripts):
                argv = shlex.split(args)
                if argv.count("--lang") != 1 or argv[argv.index("--lang") + 1] != PLACEHOLDER:
                    missing.append((os.path.basename(d), script, args))
        self.assertEqual(missing, [])

    def test_the_placeholder_is_explained(self):
        """Pasted alone, a SKILL.md must still say where {language} comes from,
        which values it takes, that missing means en, and what a refused
        language looks like."""
        values = langs()
        for d in scripts_by_skill():
            text = read("skills", os.path.basename(d), "SKILL.md")
            with self.subTest(skill=os.path.basename(d)):
                self.assertIn("`" + PLACEHOLDER + "`", text)
                self.assertIn("voice.md", text)
                self.assertIn("**Language:**", text)
                for v in values:
                    self.assertIn("`" + v + "`", text)
                self.assertRegex(text, r"no (Language )?line[^.]*`en`")
                self.assertRegex(text, r"exit 2")

    def test_every_command_runs_as_written(self):
        """Each documented command, with {language} = each language that ships
        today, is a verdict (exit 0 or 1), never a usage error or a crash."""
        for d, scripts in scripts_by_skill().items():
            text = read("skills", os.path.basename(d), "SKILL.md")
            ready = shipped(d) + ["auto"]
            self.assertIn("en", ready)
            for script, args in commands(text, scripts):
                for lang in ready:
                    with self.subTest(skill=os.path.basename(d), cmd=args, lang=lang):
                        r = self._run(os.path.join(d, script + ".py"), args, lang)
                        self.assertIn(r.returncode, (0, 1), r.stderr)
                        self.assertNotIn("Traceback", r.stderr)

    def _run(self, path, args, lang):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for name, src in FILES.items():
            shutil.copy(fixture(src), os.path.join(tmp, name))
        home = os.path.join(tmp, "home")
        os.makedirs(os.path.join(home, ".claude", "instagram"))
        values = dict(OTHER_PLACEHOLDERS, language=lang)
        argv = []
        for a in shlex.split(args):
            for name in re.findall(r"\{(\w+)\}", a):
                self.assertIn(name, values, "placeholder with no test value: {%s}" % name)
                a = a.replace("{%s}" % name, values[name])
            argv.append(a)
        argv = [os.path.join(home, a[2:]) if a.startswith("~/") else a for a in argv]
        env = dict(os.environ, HOME=home)
        return subprocess.run([sys.executable, path, *argv], cwd=tmp, env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=60)


class TemplateAndDocs(unittest.TestCase):
    def test_template_offers_exactly_the_languages(self):
        text = read("templates", "voice.md")
        m = re.search(r"^- \*\*Language:\*\* \(([^.)]*)\.", text, re.M)  # the options, up to the first stop
        self.assertTrue(m, "templates/voice.md has no **Language:** line")
        offered = re.findall(r"`([^`]+)`", m.group(1))
        self.assertEqual(sorted(offered), sorted(langs()))

    def test_readme_and_claude_md_document_the_flag(self):
        for name in ("README.md", "CLAUDE.md"):
            text = read(name)
            with self.subTest(doc=name):
                self.assertIn("--lang", text)
                for v in langs():
                    self.assertIn("`" + v + "`", text)

    def test_no_subtitle_language_pinned_to_english(self):
        """ig-viral's yt_dlp line picks a caption track by language. Asking
        for every language at once would pull YouTube's auto-translations
        (not what was said), so the SKILL.md names the track per niche."""
        text = read("skills", "ig-viral", "SKILL.md")
        self.assertIn('--sub-langs "en.*"', text)
        self.assertIn('--sub-langs "pt.*"', text)

    def test_readme_says_which_languages_ship(self):
        """"Only `en` ships today" is true until a second language file lands;
        then it must go, in the same commit."""
        anywhere = sorted({v for d in scripts_by_skill() for v in shipped(d)})
        self.assertEqual("Only `en` ships today" in read("README.md"), anywhere == ["en"])

if __name__ == "__main__":
    unittest.main()
