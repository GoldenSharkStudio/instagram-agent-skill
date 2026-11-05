"""humanize only touches what it changed.

The class (found 05/11): the cleanup meant for the spot of a deletion ran over
the whole text, so a writer's own line break, "...", "?", double space, ",\\n"
or ", also," came back rewritten, capitals included, with "0 removed" in the
report. The property has no common symbol, so this is a net, not a grep:

- every language file the folder ships (read from the folder) runs a corpus of
  clean texts, each shaped like one of those rewrites, and must come back as it
  went in;
- a line holding a deletion leaves every other line byte-equal;
- every call in humanize.py that raises a letter's case is declared here with
  its reason: a new one breaks the net, by line.
"""
import glob
import os
import re
import unittest

from _support import ROOT, load

hz = load("humanize")
HUMAN = os.path.join(ROOT, "skills", "ig-human")
LANGS = sorted(re.match(r"slop\.(.+)\.json$", os.path.basename(p)).group(1)
               for p in glob.glob(os.path.join(HUMAN, "slop.*.json")))

# Writer's text with no lexicon entry, invisible char or typographic target.
# One per rewrite the old cleanup made, in every language.
CLEAN = {
    "en": [
        "Nobody tells you this\nbefore they call.",       # line break mid-sentence
        "We waited... then it worked.",                   # ellipsis, then lower case
        "Is it late? no, it is early.",                   # answer after a question
        "We use e.g. the phone.",                         # abbreviation
        "Two  spaces here.",                              # double space
        "Wait.. what happened.",                          # two dots
        "Para one.\n\n\n\nPara two.",                     # the writer's blank lines
        "Really !",                                       # space before the mark
        "Prices: $5 . Done.",
        "It works, also, it is cheap.",                   # the writer's own comma splice
        "Hi Ana,\nthanks for the call.",                  # salutation comma
        "All good.\n  - indented item\nnext line.",
    ],
    "pt-BR": [
        "Ninguém te conta isso\nantes de ligar.",
        "Esperamos... aí funcionou.",
        "É tarde? não, é cedo.",
        "Dois  espaços aqui.",
        "Espera.. o quê.",
        "Parte um.\n\n\n\nParte dois.",
        "Sério !",
        "Funciona, também, é barato.",
        "Oi Ana,\nobrigado pela ligação.",
        "Tudo certo.\n  - item recuado\npróxima linha.",
    ],
}

# Calls that raise case, each with why it is allowed. Keyed by the stripped
# source line, so a new call (or a moved one that changed) fails by name.
RAISES_CASE = {
    "return repl.upper()": "_match_case: the replacement copies the case of the word it replaced",
    "return repl[0].upper() + repl[1:]": "_match_case: same, title case",
    'lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)':
        "_dash_to_comma: the writer's dash before a connective becomes a full stop, "
        "so the connective opens the sentence",
    "lambda m: m.group(1) + m.group(2).upper(), text)":
        "restore_capitals: only the word after a deleted sentence opener",
}
RAISE_RE = re.compile(r"\.(upper|capitalize|title|swapcase)\(")


def deletable(lex):
    """An entry humanize deletes outright and that never hangs: a phrase with an
    empty replace whose last word is not a dependent."""
    for e in lex["phrases"] + lex["words"]:
        if not e["replace"] and e["find"].split()[-1].lower() not in lex["dependents"] \
                and re.match(r"\w", e["find"][-1]):
            return e["find"]
    return None


class Coverage(unittest.TestCase):
    def test_every_language_has_a_corpus(self):
        self.assertTrue(LANGS)
        for lang in LANGS:
            self.assertIn(lang, CLEAN, f"slop.{lang}.json ships without a clean corpus here")

    def test_corpus_is_clean(self):
        # A text that trips the lexicon proves nothing about untouched text.
        for lang in LANGS:
            lex = hz.load_lexicon(lang=lang)
            for text in CLEAN[lang]:
                with self.subTest(lang=lang, text=text):
                    _, report = hz.humanize(text, lex, lang)
                    for k in ("invisible", "typographic", "lexical"):
                        self.assertEqual(report[k], [], f"fixture not clean ({k})")

    def test_every_case_raise_is_declared(self):
        src = open(os.path.join(HUMAN, "humanize.py"), encoding="utf-8").read().splitlines()
        found = {}
        for n, line in enumerate(src, 1):
            if RAISE_RE.search(line) and not line.strip().startswith("#"):
                found[line.strip()] = n
        for line, n in found.items():
            with self.subTest(line=n):
                self.assertIn(line, RAISES_CASE,
                              f"humanize.py:{n} raises case and is not declared: {line}")
        for line in RAISES_CASE:
            self.assertIn(line, found, f"declared but gone from humanize.py: {line}")


class Untouched(unittest.TestCase):
    def test_clean_text_comes_back_as_written(self):
        for lang in LANGS:
            lex = hz.load_lexicon(lang=lang)
            for text in CLEAN[lang]:
                with self.subTest(lang=lang, text=text):
                    out, _ = hz.humanize(text, lex, lang)
                    self.assertEqual(out, text.strip() + "\n")

    def test_a_deletion_leaves_the_other_lines_alone(self):
        for lang in LANGS:
            lex = hz.load_lexicon(lang=lang)
            phrase = deletable(lex)
            if phrase is None:
                # pt-BR is a skeleton (empty words/phrases) until 4b fills it.
                # Fails closed: once it has a deletable entry, it runs here.
                self.assertFalse(lex["phrases"] + lex["words"], lang)
                continue
            for text in CLEAN[lang]:
                with self.subTest(lang=lang, text=text):
                    first = f"Here it is, {phrase}."
                    out, report = hz.humanize(first + "\n" + text, lex, lang)
                    self.assertTrue(report["lexical"], f"{phrase!r} was not deleted")
                    self.assertEqual(out.split("\n", 1)[1], text.strip() + "\n")


if __name__ == "__main__":
    unittest.main()
