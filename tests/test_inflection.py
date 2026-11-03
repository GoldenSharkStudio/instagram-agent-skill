"""The lexicon inflects: "elevate" is in it, so "elevates", "elevated" and
"elevating" have to be too, each with its own grammatical replacement.

The forms a base should have are derived from the `inflection` rules in each
slop.<lang>.json, never listed here, so a base added tomorrow without its
forms breaks this file, naming the missing form. A base that does not inflect
in use is declared in `inflection.exempt` with the reason; an exemption that
no longer names a base breaks too."""

import glob
import json
import os
import re
import unittest

from _support import SKILLS, load

hz = load("humanize")
dt = load("detect")

LEXICONS = sorted(glob.glob(os.path.join(SKILLS, "ig-human", "slop.*.json")))


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def inflect(word, suffix, rules):
    for rule in rules["suffixes"][suffix]:
        if re.search(rule["pattern"], word):
            return re.sub(rule["pattern"], rule["to"], word, count=1)
    raise AssertionError(f"no {suffix!r} rule matches {word!r}")


def derived_forms(find, family, rules):
    """The forms of `find` the rules predict, inflecting the family's word."""
    spec = rules["families"][family]
    words = find.split(" ")
    at = 0 if spec["word"] == "first" else len(words) - 1
    return [" ".join(words[:at] + [inflect(words[at], s, rules)] + words[at + 1:])
            for s in spec["forms"]]


def entries(lex):
    return lex["words"] + lex["phrases"]


def bases(lex):
    """Entries of an inflecting family that are not themselves a form."""
    rules = lex["inflection"]
    return [e for e in entries(lex) if e["family"] in rules["families"] and "of" not in e]


class InflectionNet(unittest.TestCase):
    def test_every_lexicon_is_scanned(self):
        self.assertIn(os.path.join(SKILLS, "ig-human", "slop.en.json"), LEXICONS)
        for path in LEXICONS:
            with self.subTest(lexicon=os.path.basename(path)):
                self.assertIn("inflection", jload(path))

    def test_every_base_has_every_form(self):
        missing = []
        for path in LEXICONS:
            lex = jload(path)
            rules = lex["inflection"]
            have = {e["find"].lower(): e for e in entries(lex)}
            for e in bases(lex):
                if e["find"] in {x["base"] for x in rules["exempt"]}:
                    continue
                for form in derived_forms(e["find"], e["family"], rules):
                    got = have.get(form.lower())
                    if got is None or got.get("of") != e["find"]:
                        missing.append((os.path.basename(path), e["find"], form))
        self.assertEqual(missing, [])

    def test_every_form_belongs_to_its_base(self):
        """`of` names a base in the same family, and the form is one the rules
        derive from it: no orphan forms, no typos the net would not see."""
        wrong = []
        for path in LEXICONS:
            lex = jload(path)
            rules = lex["inflection"]
            by_find = {e["find"]: e for e in entries(lex)}
            for e in entries(lex):
                if "of" not in e:
                    continue
                base = by_find.get(e["of"])
                if (base is None or "of" in base or base["family"] != e["family"]
                        or e["find"] not in derived_forms(base["find"], base["family"], rules)):
                    wrong.append((os.path.basename(path), e["find"], e["of"]))
        self.assertEqual(wrong, [])

    def test_exemptions_are_live_and_explained(self):
        dead = []
        for path in LEXICONS:
            lex = jload(path)
            names = {e["find"] for e in bases(lex)}
            for x in lex["inflection"]["exempt"]:
                if set(x) != {"base", "why"} or x["base"] not in names or not x["why"].strip():
                    dead.append((os.path.basename(path), x.get("base")))
        self.assertEqual(dead, [])

    def test_rules_cover_their_families(self):
        for path in LEXICONS:
            lex = jload(path)
            rules = lex["inflection"]
            families = {e["family"] for e in entries(lex)}
            for fam, spec in rules["families"].items():
                with self.subTest(lexicon=os.path.basename(path), family=fam):
                    self.assertIn(spec["word"], ("first", "last"))
                    self.assertTrue(set(spec["forms"]) <= set(rules["suffixes"]))
                    if entries(lex):
                        self.assertIn(fam, families)

    def test_the_rules_spell_english(self):
        rules = jload(os.path.join(SKILLS, "ig-human", "slop.en.json"))["inflection"]
        for word, s, want in [("elevate", "s", "elevates"), ("elevate", "ed", "elevated"),
                              ("elevate", "ing", "elevating"), ("amplify", "s", "amplifies"),
                              ("amplify", "ed", "amplified"), ("amplify", "ing", "amplifying"),
                              ("harness", "s", "harnesses"), ("journey", "s", "journeys"),
                              ("synergy", "s", "synergies"), ("unlock", "ed", "unlocked")]:
            with self.subTest(word=word, suffix=s):
                self.assertEqual(inflect(word, s, rules), want)


class InflectedFormsWork(unittest.TestCase):
    """The witness from the finding: "elevate" was caught, "elevates" was not."""

    LEX = hz.load_lexicon()

    def test_detect_counts_the_inflected_form(self):
        self.assertTrue(dt.check_slop("This elevates the brand.", self.LEX)[1].startswith("1 stock"))

    def test_humanize_replaces_it_grammatically(self):
        self.assertEqual(hz.humanize("This elevates the brand.", self.LEX)[0],
                         "This improves the brand.\n")


if __name__ == "__main__":
    unittest.main()
