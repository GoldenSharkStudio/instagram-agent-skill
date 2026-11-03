"""hooks.json `match` per language (fase 2, passo 4a.2).

`match` is {"<lang>": regex}. swipe classifies with the regex of the language it
runs in, and with nothing else: an empty or missing regex never matches, so a
pt-BR hook is never named by an English pattern (fail closed). A language key
that is not a language the tools know is a broken schema, not a silent miss.
"""

import json
import os
import re
import shutil
import tempfile
import unittest

from _support import SKILLS, TOOLS, fixture, load, run_tool

sw = load("swipe")
HOOKS_PATH = os.path.join(SKILLS, "ig-reel", "hooks.json")
CODES = [c for c in sw.LANGS if c != "auto"]


def hooks():
    with open(HOOKS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["hooks"]


def plant(d, formulas):
    path = os.path.join(d, "hooks.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"hooks": formulas, "classify_order": [f["id"] for f in formulas]}, fh)
    return path


class RepoSchema(unittest.TestCase):
    def test_every_match_is_keyed_by_every_language(self):
        # Every formula carries a slot per language, so 4b fills strings and
        # never edits the schema; a slot for an unknown code is a typo.
        for h in hooks():
            with self.subTest(id=h["id"]):
                self.assertIsInstance(h["match"], dict)
                self.assertEqual(sorted(h["match"]), sorted(CODES))
                self.assertTrue(all(isinstance(v, str) for v in h["match"].values()))
                self.assertTrue(h["match"]["en"].strip())

    def test_every_non_empty_match_compiles(self):
        for h in hooks():
            for code, rx in h["match"].items():
                if rx:
                    with self.subTest(id=h["id"], lang=code):
                        re.compile(rx, re.IGNORECASE)

    def test_en_loads_all_formulas(self):
        self.assertEqual(len(sw.load_formulas(HOOKS_PATH, "en")), len(hooks()))

    def test_load_defaults_to_en(self):
        self.assertEqual([f[0] for f in sw.load_formulas(HOOKS_PATH)],
                         [f[0] for f in sw.load_formulas(HOOKS_PATH, "en")])


class FailsClosed(unittest.TestCase):
    """The language picks the regex; no language ever borrows another's."""

    def test_empty_slot_never_matches(self):
        # Today every pt-BR slot is empty: an English example run as pt-BR is
        # unclassified, never named by the English regex.
        formulas = sw.load_formulas(HOOKS_PATH, "pt-BR")
        for h in hooks():
            if h["match"]["pt-BR"]:
                continue
            with self.subTest(id=h["id"]):
                self.assertNotIn(h["id"], [f[0] for f in formulas])
                fid, _ = sw.classify(h["example"], formulas)
                self.assertIsNone(fid)

    def test_each_language_uses_its_own_regex(self):
        with tempfile.TemporaryDirectory() as d:
            path = plant(d, [{"id": 1, "name": "One",
                              "match": {"en": r"\bcost me\b", "pt-BR": r"\bme custou\b"}}])
            en, pt = sw.load_formulas(path, "en"), sw.load_formulas(path, "pt-BR")
        self.assertEqual(sw.classify("It cost me a client", en)[0], 1)
        self.assertIsNone(sw.classify("It cost me a client", pt)[0])
        self.assertEqual(sw.classify("Isso me custou um cliente", pt)[0], 1)
        self.assertIsNone(sw.classify("Isso me custou um cliente", en)[0])

    def test_missing_slot_never_matches(self):
        with tempfile.TemporaryDirectory() as d:
            path = plant(d, [{"id": 1, "name": "One", "match": {"en": r"\bcost me\b"}}])
            self.assertEqual(sw.load_formulas(path, "pt-BR"), [])

    def test_legacy_string_match_is_english_only(self):
        # A hooks.json edited before 4a.2 keeps working in English and never
        # classifies another language with its English regex.
        with tempfile.TemporaryDirectory() as d:
            path = plant(d, [{"id": 1, "name": "One", "match": r"\bcost me\b"}])
            self.assertEqual(sw.classify("It cost me", sw.load_formulas(path, "en"))[0], 1)
            self.assertEqual(sw.load_formulas(path, "pt-BR"), [])

    def test_bad_schema_is_named(self):
        bad = {
            "unknown language key": {"en": "x", "pt_BR": "y"},
            "non-string regex": {"en": 3},
            "list instead of dict": ["x"],
            "broken regex in another language": {"en": "x", "pt-BR": "("},
        }
        for why, match in bad.items():
            with self.subTest(why=why), tempfile.TemporaryDirectory() as d:
                path = plant(d, [{"id": 1, "name": "One", "match": match}])
                with self.assertRaises(sw.HooksError):
                    sw.load_formulas(path, "en")


class Cli(unittest.TestCase):
    def test_explicit_hooks_with_unknown_language_key_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            path = plant(d, [{"id": 1, "name": "One", "match": {"en": "x", "pt_BR": "y"}}])
            proc = run_tool("swipe", fixture("captured.tsv"), "--hooks", path)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("pt_BR", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_no_formula_for_the_language_says_so(self):
        # Loaded fine but nothing to match in this language: the note says that,
        # not "hooks.json not found".
        with tempfile.TemporaryDirectory() as d:
            path = plant(d, [{"id": 1, "name": "One", "match": {"pt-BR": r"\bme custou\b"}}])
            proc = run_tool("swipe", fixture("captured.tsv"), "--hooks", path, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("not found", proc.stderr)
        self.assertIn("no `match` for en", proc.stderr)
        self.assertTrue(all(r["formula_id"] is None for r in json.loads(proc.stdout)["reels"]))

    def test_broken_default_language_key_still_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.dirname(TOOLS["swipe"]), os.path.join(d, "ig-viral"))
            os.makedirs(os.path.join(d, "ig-reel"))
            plant(os.path.join(d, "ig-reel"),
                  [{"id": 1, "name": "One", "match": {"en": "x", "pt_BR": "y"}}])
            proc = run_tool(os.path.join(d, "ig-viral", "swipe.py"), fixture("captured.tsv"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
