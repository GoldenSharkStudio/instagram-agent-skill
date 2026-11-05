"""One answer to "is this concrete?" in every tool that asks it.

The class (found in the real cycle, 04/11): caption and beats shared one regex,
hookscore had its own figures with units and spoken numbers, detect had its own
numbers and names. "23h" counted in hookscore and nowhere else; a month in
Portuguese ("março") and an acronym ("EUA") counted nowhere. The same hook got
a different verdict depending on which tool read it. The property has no
common symbol, so this is a net:

- every script is read for a concreteness rule (a capital-letter name class, a
  figure, a price) outside `build_concrete`: a new one breaks the net by line,
  unless it is declared below with its reason;
- the scripts that call `concrete_marks` all carry the same two functions, and
  every one of them has an adapter here (a new caller without one fails);
- the `concrete` section of every language file is the same in each folder;
- the same phrases, per language, are concrete (or not) in every tool, read
  through each tool's own verdict, not through the shared function.
"""
import ast
import glob
import json
import os
import tempfile
import unittest

from _support import ROOT, SKILLS, TOOLS, load, run_tool
from test_lang import INPUT, edit_json, lone_copy

SHARED = ("build_concrete", "concrete_marks")

# Strings in a script that look like a concreteness rule and are not one.
EXEMPT = {
    ("hookscore", r"\$\s?\d"): "STAKES: a price is something to lose, a stake, "
                               "counted on top of being concrete",
}
SHAPES = ("A-ZÀ", r"\b\d", r"\$\s?\d")


def tool_of(path):
    return next(t for t, p in TOOLS.items() if os.path.realpath(p) == os.path.realpath(path))


def trees():
    for tool, path in TOOLS.items():
        with open(path, encoding="utf-8") as fh:
            yield tool, ast.parse(fh.read(), path)


def calls(tree, name):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
               for n in ast.walk(tree))


# --- adapters: each tool's own verdict on one phrase --------------------------

def via_hookscore(text, lang):
    mod = load("hookscore")
    score, _ = mod.check_specificity(text, mod.load_lang(lang))
    return score > 15.0


def via_beats(text, lang):
    return load("beats").analyse(text, lang=lang)["beats"][0]["concrete"] > 0


def via_caption(text, lang):
    a = load("caption").analyse(text, lang=lang)
    return next(c for c in a["checks"] if c["check"] == "HOOK IS CONCRETE")["status"] == "PASS"


PAD = {"en": "and so the thing is that it goes on and on the way it always does " * 2,
       "pt-BR": "e aí a coisa é que ela vai e vai do jeito que sempre vai mesmo " * 2}


def via_detect(text, lang):
    mod = load("detect")
    base, _ = mod.check_specificity(PAD[lang], lang)
    score, _ = mod.check_specificity(PAD[lang] + "\n" + text, lang)
    return score > base


ADAPTERS = {"hookscore": via_hookscore, "beats": via_beats,
            "caption": via_caption, "detect": via_detect}

# Written from scratch, one shape per line. Each must be concrete everywhere.
CONCRETE = {
    "en": [
        "The bakery closes at 11pm",                 # clock time
        "The bakery opens at 9:30",
        "We opened in march",                # a month, lower case
        "March was the slow one",            # a month opening the line
        "Most clients live in the USA",      # acronym of a place
        "It costs $7 a day",                 # price
        "We got 3 calls",                    # figure
        "We got 3,000 views",
        "It took 8s to load",
        "Seven clients said yes",            # spoken number
        "The rent went up",                  # money word
        "Then Maria called back",            # a name inside the line
    ],
    "pt-BR": [
        "A padaria fecha às 23h",
        "A padaria abre às 9:30",
        "Abrimos em março",
        "Março foi o mês fraco",
        "Meu primo mora nos EUA",
        "Custa R$ 7 por dia",
        "Recebemos 3 ligações",
        "Recebemos 3.000 visitas",
        "Levou 8s para abrir",
        "Sete clientes disseram sim",
        "O aluguel subiu",
        "Aí a Maria ligou de volta",
    ],
}

# Each must be abstract everywhere.
ABSTRACT = {
    "en": [
        "You need to grow your brand",
        "Nobody cares. Then it hits you",            # a capital after a full stop
        "It may work for you",                       # "may" is a verb here
        "WHILE YOU WAIT THE PHONE RINGS FOR HIM",    # shouting is not acronyms
        "Send me a DM and I will tell you",          # DM is not a place or a thing
        "OK so here is the thing",
    ],
    "pt-BR": [
        "Você precisa crescer sua marca",
        "Ninguém liga. Depois dói",
        "ENQUANTO VOCÊ ESPERA ELE BATE NA PORTA",
        "Me manda uma DM que eu te conto",
        "OK então é o seguinte",
    ],
}


class TheNetSeesTheTree(unittest.TestCase):
    def test_no_rule_outside_the_shared_function(self):
        found = []
        for tool, tree in trees():
            inside = set()
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name in SHARED:
                    inside |= {id(n) for n in ast.walk(node)}
            for n in ast.walk(tree):
                if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and id(n) not in inside and n.lineno > 1
                        and any(s in n.value for s in SHAPES)
                        and (tool, n.value) not in EXEMPT):
                    found.append(f"{tool}:{n.lineno} {n.value[:50]!r}")
        self.assertEqual(found, [], "a concreteness rule outside build_concrete")

    def test_exemptions_are_live(self):
        for (tool, value), why in EXEMPT.items():
            with self.subTest(tool=tool, value=value):
                with open(TOOLS[tool], encoding="utf-8") as fh:
                    src = fh.read()
                self.assertIn(value, src, why)

    def test_every_caller_has_an_adapter_and_the_same_copy(self):
        copies, callers = {}, set()
        for tool, tree in trees():
            if calls(tree, "concrete_marks"):
                callers.add(tool)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name in SHARED:
                    copies.setdefault(node.name, {})[tool] = ast.dump(node)
        self.assertEqual(sorted(callers), sorted(ADAPTERS), "a caller without an adapter")
        for name in SHARED:
            with self.subTest(function=name):
                self.assertEqual(sorted(copies.get(name, {})), sorted(callers))
                self.assertEqual(len(set(copies[name].values())), 1, sorted(copies[name]))


class OneSectionPerLanguage(unittest.TestCase):
    def test_concrete_section_is_the_same_in_every_folder(self):
        folders = {os.path.dirname(TOOLS[t]) for t in ADAPTERS}
        by_lang = {}
        for folder in sorted(folders):
            for path in glob.glob(os.path.join(folder, "lang", "*.json")):
                with open(path, encoding="utf-8") as fh:
                    section = json.load(fh).get("concrete")
                self.assertIsNotNone(section, os.path.relpath(path, ROOT))
                code = os.path.basename(path)[:-5]
                by_lang.setdefault(code, {})[os.path.relpath(path, SKILLS)] = section
        self.assertEqual(sorted(by_lang), sorted(CONCRETE))
        for code, sections in by_lang.items():
            with self.subTest(lang=code):
                self.assertEqual(len(sections), len(folders), sorted(sections))
                first = next(iter(sections.values()))
                self.assertEqual([p for p, s in sections.items() if s != first], [])


class SameVerdictEverywhere(unittest.TestCase):
    def check(self, table, want):
        wrong = []
        for lang, phrases in table.items():
            for text in phrases:
                for tool, ask in ADAPTERS.items():
                    if ask(text, lang) is not want:
                        wrong.append(f"{tool} [{lang}] {text!r}")
        self.assertEqual(wrong, [])

    def test_concrete_phrases(self):
        self.check(CONCRETE, True)

    def test_abstract_phrases(self):
        self.check(ABSTRACT, False)

    def test_tables_cover_every_language(self):
        self.assertEqual(sorted(CONCRETE), sorted(ABSTRACT))


class FrontloadFindsTheWord(unittest.TestCase):
    def test_a_marker_inside_a_word_is_that_word(self):
        hs = load("hookscore")
        L = hs.load_lang("pt-BR")
        # No STAKES word in these, so the marker is the payload.
        for text, position in (("R$7 por dia muda tudo", 1), ("O lanche de R$ 7 acabou", 4),
                               ("Hoje a Maria abriu", 3)):
            with self.subTest(text=text):
                self.assertIn(f" {position}", hs.check_frontload(text, L)[1])


class MissingSectionFailsClosed(unittest.TestCase):
    """Each tool reads `concrete` from its folder's own language file."""

    def check(self, tool, change):
        arg, stdin = INPUT[tool]
        with tempfile.TemporaryDirectory() as d:
            script, _ = lone_copy(d, tool)
            lang = os.path.join(os.path.dirname(script), "lang", "en.json")
            edit_json(lang, change)
            proc = run_tool(script, arg, stdin=stdin)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("en.json", proc.stderr)

    def test_missing_section(self):
        for tool in ADAPTERS:
            with self.subTest(tool=tool):
                self.check(tool, lambda j: j.pop("concrete"))

    def test_missing_key(self):
        for tool in ADAPTERS:
            with self.subTest(tool=tool):
                self.check(tool, lambda j: j["concrete"].pop("caps_skip"))

    def test_bad_unit_regex(self):
        def bad(j):
            j["concrete"]["number_units"] = "(unclosed"
        for tool in ADAPTERS:
            with self.subTest(tool=tool):
                self.check(tool, bad)


if __name__ == "__main__":
    unittest.main()
