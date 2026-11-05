"""A lexicon replacement has to fit the word's real uses, not just its
dictionary sense: "Sales skyrocketed" is not "Sales raised", "an innovative
format" is not "an new format", "my secret sauce" is not "my the actual method".

tests/fixtures/lexicon_uses.<lang>.json holds real sentences for every `words`
entry of slop.<lang>.json, each with the sentence humanize should give back,
written by hand. Every entry has to fire in at least one of them: the entries
come from the lexicon, never from a list here, so an entry added tomorrow
without a use breaks this file, naming it. A lexicon with words and no
fixture breaks too.

`phrases` are out of this net: each is a whole clause (an opener, a closer, a
call to action) replaced or deleted as a unit, so it has no grammatical role
that changes with the sentence; tests/test_human.py runs every entry, phrases
included, in fixed places and every deletion through the hanging net."""

import glob
import json
import os
import unittest

from _support import FIXTURES, SKILLS, load

hz = load("humanize")

LEXICONS = sorted(glob.glob(os.path.join(SKILLS, "ig-human", "slop.*.json")))


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def lang_of(path):
    return os.path.basename(path)[len("slop."):-len(".json")]


def fixture_for(lang):
    return os.path.join(FIXTURES, f"lexicon_uses.{lang}.json")


def fired(text, lex):
    """The entries that changed or held something in `text`, by find."""
    _, hits, held = hz.pass_lexical(hz.pass_typographic(text, lex)[0], lex)
    return {h["find"].lower() for h in hits}, {h["find"].lower() for h in held}


class EveryWordHasARealUse(unittest.TestCase):
    def test_every_lexicon_with_words_has_a_fixture(self):
        for path in LEXICONS:
            lex = jload(path)
            if lex["words"]:
                self.assertTrue(os.path.exists(fixture_for(lang_of(path))),
                                f"{os.path.basename(path)} has words and no "
                                f"lexicon_uses.{lang_of(path)}.json")

    def test_every_entry_fires_in_a_use(self):
        for path in LEXICONS:
            lex = jload(path)
            if not lex["words"]:
                continue
            uses = jload(fixture_for(lang_of(path)))["uses"]
            seen = set()
            for u in uses:
                hits, held = fired(u["text"], lex)
                seen |= hits | held
            missing = [e["find"] for e in lex["words"] if e["find"].lower() not in seen]
            self.assertEqual(missing, [], f"{os.path.basename(path)}: entries with no use")


class TheReplacementFitsTheUse(unittest.TestCase):
    def test_humanize_gives_back_the_wanted_sentence(self):
        for path in LEXICONS:
            lang = lang_of(path)
            if not os.path.exists(fixture_for(lang)):
                continue
            lex = hz.load_lexicon(path)
            wrong = []
            for u in jload(fixture_for(lang))["uses"]:
                out = hz.humanize(u["text"], lex, lang)[0].strip()
                if out != u["want"]:
                    wrong.append(f"{u['text']!r}\n      got  {out!r}\n      want {u['want']!r}")
            self.assertEqual(wrong, [], f"{lang}: {len(wrong)} uses broken\n    " + "\n    ".join(wrong))

    def test_the_report_names_the_replacement_made(self):
        # A role gives its own word: the report has to say "shot up", not
        # the entry's "boosted", or it describes a change that never happened.
        for path in LEXICONS:
            lang = lang_of(path)
            if not os.path.exists(fixture_for(lang)):
                continue
            lex = hz.load_lexicon(path)
            wrong = []
            for u in jload(fixture_for(lang))["uses"]:
                out, report = hz.humanize(u["text"], lex, lang)
                for h in report["lexical"]:
                    if h["replace"] != hz.say(hz.load_messages(lang), "deleted") \
                            and h["replace"].lower() not in out.lower():
                        wrong.append(f"{u['text']!r}: report says {h['find']} -> {h['replace']}, got {out.strip()!r}")
            self.assertEqual(wrong, [], "\n".join(wrong))

    def test_a_word_with_no_safe_replacement_is_held_and_flagged(self):
        for path in LEXICONS:
            lang = lang_of(path)
            if not os.path.exists(fixture_for(lang)):
                continue
            lex = hz.load_lexicon(path)
            wrong = []
            for u in jload(fixture_for(lang))["uses"]:
                _, held = fired(u["text"], lex)
                if held != set(u.get("held", [])):
                    wrong.append(f"{u['text']!r}: held {sorted(held)}, want {u.get('held', [])}")
            self.assertEqual(wrong, [], "\n".join(wrong))


if __name__ == "__main__":
    unittest.main()
