"""Class net for "a regex meant to match letters only matches ASCII".

The tools are going to read Portuguese. `[A-Za-z]` splits "você" into "voc",
turns "#ação" into "#a" and does not see "Érica" as a name. The fix is not
one regex: it is every character class in every script and every JSON regex
that names an ASCII letter range. So the net reads them from src:

1. `ascii_classes` finds every `[...]` holding `A-Z` or `a-z` without the
   Latin-1 letters next to it, in every string literal of every script and in
   every regex of every JSON. Anything it finds must be declared in EXEMPT.
2. Each member then gets a witness that only passes if it matches the
   accented word the way it matches the plain one.

Python's `re` has no \\p{Lu}, so the letter class is `[^\\W\\d_]` (any
Unicode letter) and the case classes add Latin-1: `A-ZÀ-ÖØ-Þ` / `a-zß-öø-ÿ`.
That covers pt-BR, es, fr and de; Latin Extended-A (Polish, Czech, Turkish)
is out of scope until a language that needs it is added.
"""

import ast
import json
import os
import re
import unittest

from _support import ROOT, SKILLS, load, run_json
from test_invariants import REGEX_KEYS, data_strings, script_paths

# A class with an ASCII letter range that does not also carry the Latin-1
# letters for the same case. "À-Ö" is the upper half, "ß-ö" the lower one.
_RANGE = re.compile(r"A-Z|a-z")


def _classes(pattern):
    """Every top-level [...] in a regex source, escapes respected."""
    out, i, n = [], 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and pattern[j] == "^":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 2 if pattern[j] == "\\" else 1
            out.append(pattern[i:j + 1])
            i = j + 1
            continue
        i += 1
    return out


def ascii_classes(pattern):
    bad = []
    for cls in _classes(pattern):
        if cls.startswith("[^"):
            continue  # a negated class excludes, it does not decide what a letter is
        if ("A-Z" in cls and "À-Ö" not in cls) or ("a-z" in cls and "ß-ö" not in cls):
            bad.append(cls)
    return bad


def source_regexes():
    """(where, pattern) for every string literal in every script that holds
    an ASCII letter range, plus every regex string in the JSON data."""
    out = []
    for path in script_paths():
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        rel = os.path.relpath(path, ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and _RANGE.search(node.value):
                out.append((f"{rel}:{node.lineno}", node.value))
    for f, k, v in data_strings():
        if k in REGEX_KEYS:
            out.append((f"{f}[{k}]", v))
    return out


# Members that stay ASCII on purpose. Keyed by (file, class) so a new ASCII
# class elsewhere in the same file is not covered by an old reason.
EXEMPT = {
    ("skills/ig-caption/caption.py", "[A-Za-z0-9_.]"):
        "MENTION_RE: an Instagram handle is ASCII letters, digits, _ and . by "
        "platform rule; '@joão' is not a handle Instagram would link",
    ("skills/ig-caption/caption.py", "[a-z0-9-]"):
        "LINK_RE bare domain: a DNS label as typed in a caption; IDN domains "
        "show up as punycode (xn--, ASCII) or with a scheme, which \\S+ already takes",
    ("skills/ig-caption/caption.py", "[a-z]"):
        "LINK_RE country code after .com (\"loja.com.br/x\"): an ISO 3166 code, ASCII by DNS rule",
    ("skills/ig-human/humanize.py", "[a-z0-9-]"):
        "URL_RE bare domain, the same DNS label as caption LINK_RE (tests/test_links.py keeps them in step)",
    ("skills/ig-human/humanize.py", "[a-z]"):
        "URL_RE country code, same as caption LINK_RE",
}


class AsciiOnlyNet(unittest.TestCase):
    def test_detector_sees_a_planted_ascii_class(self):
        self.assertEqual(ascii_classes(r"\b[A-Z][a-z]{2,}\b"), ["[A-Z]", "[a-z]"])
        self.assertEqual(ascii_classes(r"[A-Za-z0-9$%'-]+"), ["[A-Za-z0-9$%'-]"])
        self.assertEqual(ascii_classes(r"\b[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]{2,}\b"), [])
        self.assertEqual(ascii_classes(r"[^A-Za-z]"), [])
        self.assertEqual(ascii_classes(r"\[A-Z\]"), [])
        self.assertEqual(ascii_classes(r"[\]A-Z]"), [r"[\]A-Z]"])

    def test_the_scan_reached_the_src(self):
        where = {w.split(":")[0].split("[")[0] for w, _ in source_regexes()}
        self.assertIn("skills/ig-caption/caption.py", where)   # the exempt ones
        self.assertGreater(len([w for w in where if w.endswith(".json")]), 3)

    def test_no_ascii_only_letter_class(self):
        bad, used = [], set()
        for where, pattern in source_regexes():
            path = where.split(":")[0].split("[")[0]
            for cls in ascii_classes(pattern):
                if (path, cls) in EXEMPT:
                    used.add((path, cls))
                else:
                    bad.append((where, cls))
        self.assertEqual(bad, [], "ASCII-only letter class: use [^\\W\\d_] or add Latin-1")
        self.assertEqual(set(EXEMPT) - used, set(), "exemption no longer matches anything: remove it")


class AccentedWitnesses(unittest.TestCase):
    """Each member matches the accented word the way it matches the plain one."""

    def test_word_re_keeps_accented_words_whole(self):
        for tool in ("hookscore", "beats", "swipe", "detect"):
            with self.subTest(tool=tool):
                words = load(tool).WORD_RE.findall("Você perdeu a ação, Été")
                self.assertEqual(words, ["Você", "perdeu", "a", "ação", "Été"])

    def test_word_re_still_splits_on_underscore_and_keeps_its_symbols(self):
        # The fix widens letters, nothing else: same tokens as before on ASCII.
        for tool in ("hookscore", "beats", "swipe"):
            with self.subTest(tool=tool):
                self.assertEqual(load(tool).WORD_RE.findall("I made $18,000 (40%) don't co-op a_b"),
                                 ["I", "made", "$18", "000", "40%", "don't", "co-op", "a", "b"])
        self.assertEqual(load("detect").WORD_RE.findall("don't 40% a_b"), ["don't", "a", "b"])

    def test_proper_names_with_accents(self):
        text = "Ontem a Érica abriu em São Paulo."
        self.assertEqual(set(load("hookscore").PROPER_RE.findall(text)), {"Érica", "São", "Paulo"})
        self.assertEqual(set(load("detect").PROPER.findall(text)), {"Érica", "São", "Paulo"})
        for tool in ("beats", "caption"):
            with self.subTest(tool=tool):
                self.assertEqual(load(tool).CONCRETE_RE.findall(text), ["Érica", "São", "Paulo"])

    def test_proper_still_wants_a_lower_case_tail(self):
        for found in (load("hookscore").PROPER_RE.findall("x ÉRICA NASA Ok"),
                      load("detect").PROPER.findall("x ÉRICA NASA Ok")):
            self.assertEqual(found, [])

    def test_hashtag_keeps_the_whole_tag(self):
        _, out = run_json("caption", "-", stdin="Leia isto.\n\n#ação #marketing_digital #café\n")
        self.assertEqual(out["hashtags"], ["#ação", "#marketing_digital", "#café"])
        self.assertEqual(load("hookscore").HASHTAG_RE.findall("isso #ação"), ["#ação"])

    def test_restore_capitals_after_an_accented_opener(self):
        hz = load("humanize")
        d = hz.DELETED   # the mark a deleted opener leaves until cleanup
        self.assertEqual(hz.restore_capitals("Ótimo. Ética conta. Árvore.", f"{d} ética conta."),
                         f"{d} Ética conta.")
        # A lower-case voice that starts on an accented letter stays lower case.
        self.assertEqual(hz.restore_capitals("ótimo. ética. árvore.", f"{d} ética."),
                         f"{d} ética.")

    def test_caps_shout_tell_counts_accented_words(self):
        caps = next(s for s in load("humanize").load_lexicon()["structures"]
                    if s["id"] == "caps-shout")
        rx = re.compile(caps["regex"], re.MULTILINE)
        self.assertEqual(len(rx.findall("ATENÇÃO: VOCÊ PRECISA VER")), 1)
        self.assertEqual(len(rx.findall("STOP DOING THIS")), 1)
        self.assertEqual(len(rx.findall("Atenção você precisa")), 0)

    def test_comment_keyword_ask_takes_an_accented_word(self):
        asks = load("caption").load_lang()["ASKS"]
        hit = [n for rx, n, _ in asks if rx.search('Comment "AÇÃO" below')]
        self.assertIn("comment a keyword", hit)

    def test_hook_formulas_open_on_an_accented_letter(self):
        # swipe compiles `match` with IGNORECASE; so does this. The formulas are
        # found by the shape that follows their opening letter, not by a
        # hand-written id, so the witness follows the data.
        with open(os.path.join(SKILLS, "ig-reel", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        callout = [f for f in hooks if r"][\w ]{2,28}" in f["match"]["en"]]
        verdict = [f for f in hooks if r"][\w' ]{2,34}" in f["match"]["en"]]
        self.assertEqual((len(callout), len(verdict)), (1, 1))
        for f, text in ((callout[0], "Ótimos designers: stop doing this"),
                        (verdict[0], "Ágile coaching is overrated")):
            with self.subTest(formula=f["id"]):
                self.assertTrue(re.compile(f["match"]["en"], re.IGNORECASE).search(text))


if __name__ == "__main__":
    unittest.main()
