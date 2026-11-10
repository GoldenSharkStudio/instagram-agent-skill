"""A deletion leaves no punctuation behind, wherever it sits in the line.

humanize deletes a stock word or phrase whole ("Importantly", "follow for
more"). The punctuation around it belonged to it: "It works. Importantly, it
is cheap." gave "It works., It is cheap.", a copy-ready caption worse than the
slop it came from. The tests in test_human.py only put a deletion at the start
of a line, where the old cleanup worked.

The entries come from every slop.<lang>.json (each one whose `replace` is
empty), never from a list here, so an entry added tomorrow runs through every
place below. The sentence each place should give back is written by hand, once
per place, and holds for any deleted entry."""

import glob
import json
import os
import unittest

from _support import SKILLS, load

hz = load("humanize")

LEXICONS = sorted(glob.glob(os.path.join(SKILLS, "ig-human", "slop.*.json")))

# {X}: the entry as it opens a sentence, {x}: as it sits inside one.
# Left: what the writer sent. Right: what the reader must get, by hand.
PLACES = [
    # after a sentence that ends on the same line
    ("It works. {X}, it is cheap.", "It works. It is cheap."),
    ("Wow! {X}, it works.", "Wow! It works."),
    ("Why? {X}, it is cheap.", "Why? It is cheap."),
    ("Done!! {X}, it is cheap.", "Done!! It is cheap."),
    ("It works.{X}, it is cheap.", "It works. It is cheap."),
    ("It works. {X}; it is cheap.", "It works. It is cheap."),
    ("It works. {X}: it is cheap.", "It works. It is cheap."),
    ("It works. {X} — it is cheap.", "It works. It is cheap."),
    ("It works. {X}, {x}, it is cheap.", "It works. It is cheap."),
    ("It works. {X}!", "It works."),
    ("It works. {X}.", "It works."),
    # after a colon or a semicolon: the clause goes on in lower case
    ("Note: {x}, it is cheap.", "Note: it is cheap."),
    ("It works; {x}, it is cheap.", "It works; it is cheap."),
    ("It works; {x}.", "It works."),
    # inside a sentence, between two commas. A word there is an aside and both
    # commas were its own. A phrase is a clause: one comma stays, or the two
    # sides run together ("I tried it, here's the thing, it works" would give
    # "I tried it it works").
    ("We grew, {x}, in March.", {"word": "We grew in March.",
                                 "phrase": "We grew, in March."}),
    ("We grew, {x}.", "We grew."),
    # where the old cleanup already worked: these must not move
    ("{X}, it is cheap.", "It is cheap."),
    ("It works.\n{X}, it is cheap.", "It works.\nIt is cheap."),
    ("It works. {X} it is cheap.", "It works. It is cheap."),
]


def deletions(lex):
    return [e for e in lex["words"] + lex["phrases"] if not e["replace"]]


def forms(find):
    return {"X": find[0].upper() + find[1:], "x": find}


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class ADeletionLeavesNoPunctuation(unittest.TestCase):
    def test_the_net_is_not_empty(self):
        # A lexicon renamed or emptied would make every test below pass on
        # nothing. pt-BR has no terms yet; en has to carry deletions.
        self.assertTrue(any(deletions(jload(p)) for p in LEXICONS),
                        "no deletion entry in any slop.*.json")

    def test_the_site_pattern_knows_the_mark(self):
        # SITE_RE spells DELETED out to stay a literal: a new mark must not
        # leave it matching nothing.
        self.assertTrue(hz.SITE_RE.search("." + hz.DELETED + ","))

    def test_every_deletion_in_every_place(self):
        bad = []
        for path in LEXICONS:
            lang = os.path.basename(path)[len("slop."):-len(".json")]
            lex = hz.load_lexicon(path)
            for entry in deletions(lex):
                fired = 0
                kind = "phrase" if any(c.isspace() for c in entry["find"]) else "word"
                for src, want in PLACES:
                    if isinstance(want, dict):
                        want = want[kind]
                    text = src.format(**forms(entry["find"]))
                    got, report = hz.humanize(text, lex, lang)
                    if entry["find"].lower() in got.lower():
                        continue      # held (a clause would hang): the report flags it
                    fired += 1
                    if got != want + "\n":
                        bad.append(f"{lang} {entry['find']!r}: {text!r} -> {got!r}, want {want!r}")
                if not fired:
                    bad.append(f"{lang} {entry['find']!r}: deleted in no place, so nothing here tests it")
        self.assertEqual(bad, [], f"{len(bad)} deletion(s) left punctuation:\n" + "\n".join(bad[:40]))


if __name__ == "__main__":
    unittest.main()
