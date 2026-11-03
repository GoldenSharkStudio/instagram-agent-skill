"""Class net for the typographic apostrophe.

iOS types "’" for "'" on its own. The data regexes spell apostrophes as "'"
("what'?s", "don'?t") and the word lists hold "don't", so a hook typed on a
phone ("What’s up, guys") slipped past every one of them. The fix (owner's
call, 02/11) is to normalise the copy each script matches against, never to
touch the user's text and never to rewrite the regexes.

The net is derived from the source, not listed by hand:
  1. members:   every JSON string under skills/ that holds a "'" and sits
                under a key the scripts match with (MATCH_KEYS);
  2. invariant: every script that reads that JSON answers the same for the
                witness typed with "'" and with "’";
  3. coverage:  a "'" under a key the net does not know fails, and so does a
                regex member no witness exercises, and a tool with no entry.
"""

import json
import os
import re
import unittest

from _support import ROOT, TOOLS, load
from test_invariants import REGEX_KEYS, data_strings

CURLY = "’"

# Keys whose strings are matched against user text.
TERM_KEYS = {"find", "stakes", "weak_openers", "imperatives"}
MATCH_KEYS = REGEX_KEYS | TERM_KEYS

# Keys that hold prose for a person to read, never matched. Declared, with
# the reason, so an exemption is a decision and not a hole.
DISPLAY_KEYS = {
    "name": "label shown in reports",
    "fix": "advice shown to the user",
    "to": "replacement written out, not matched",
    "trap": "hooks.json advice for the model",
    "example": "hooks.json sample for the model",
    "on_screen": "hooks.json sample for the model",
    "rules": "hooks.json advice for the model",
    "best_for": "hooks.json advice for the model",
    "hashtags_over": "caption.py message, printed (tests/test_messages.py owns the messages)",
    "common_fail": "rubric.json, read by the model, not by code",
    "full_marks": "rubric.json, read by the model, not by code",
    "note": "comment for the person editing the JSON, read by no tool",
    "why": "reason an inflection is exempt, read by the test suite only",
}

# Sentences a person would type. The coverage guard below fails, naming the
# regex, if a regex member is not exercised by any of them.
WITNESSES = [
    "Don't scroll past this one.",
    "Wait, don't scroll.",
    "Don't buy a new camera yet.",
    "In today's video I'll show you how I price.",
    "I'm going to show you the exact script.",
    "Today I'm going to show you my setup.",
    "What's up guys, here is the plan.",
    "What's the one thing nobody tells you about pricing?",
    "You're doing it wrong if you charge by the hour.",
    "Here's the exact script I send to clients.",
    "You don't need a bigger audience.",
    "And that's when the client called back.",
    "It's not just a logo, it's a promise.",
    "This isn't about money. It's about time.",
    "Here's what I learned from 40 clients.",
    "We'll do $500 in a single week.",
    "You're doing pricing all wrong.",
    "'Just raise your prices,' sure.",
    "'How do you price a logo?' I get this daily.",
    "Canva's free plan is overrated.",
]

# Regexes where the apostrophe is redundant: another alternative already
# matches the curly form, so no witness can show the difference. Declared so
# the exemption is visible; test_redundant_exemptions_are_live keeps it true.
REDUNDANT = {
    r"\b(you|your|you're|youre|yourself)\b": "`you\\b` already matches \"You’re\"",
}


def curly(text):
    return text.replace("'", CURLY)


def members():
    return [(f, k, v) for f, k, v in data_strings() if "'" in v and k in MATCH_KEYS]


def term_witness(term):
    return term[:1].upper() + term[1:] + " pay the rent on time."


def witnesses_for(key, value):
    if key in TERM_KEYS:
        return [term_witness(value)]
    if value in REDUNDANT:
        return []
    # A witness counts only if the apostrophe is what makes it match: the
    # straight form matches the raw regex and the curly form does not.
    pat = re.compile(value, re.IGNORECASE | re.MULTILINE)
    return [w for w in WITNESSES if pat.search(w) and not pat.search(curly(w))]


def readers(data_file):
    """Tools that read `data_file`, from their source: the file is named in
    it, or it sits in the tool's lang/ folder and the tool loads LANG_DIR."""
    path = os.path.join(ROOT, data_file)
    out = []
    for name, tool in TOOLS.items():
        with open(tool, encoding="utf-8") as fh:
            src = fh.read()
        in_lang = os.path.dirname(path) == os.path.join(os.path.dirname(tool), "lang")
        named = re.search(r"(?<![\w.])" + re.escape(os.path.basename(path)), src)
        if named or (in_lang and "LANG_DIR" in src):
            out.append(name)
    return out


def canon(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False).replace(CURLY, "'"))


# Neutral words, no apostrophe: VOICE only measures past 25 words.
PAD = (" We sat down on Monday and wrote the plan on paper first, then we "
       "called the printer and asked for the price of five hundred copies.")


def _detect(text):
    dt = load("detect")
    lex = dt.load_lexicon()
    text += PAD
    results, _, _ = dt.run(text, lex)
    # FINGERPRINT counts curly quotes on purpose (a machine tell), and the
    # overall score and verdict carry it. Everything else must agree, and
    # the tells that hold the verdict are compared on their own.
    out = {k: v for k, v in results.items() if k != "FINGERPRINT"}
    out["tells"] = dt.count_tells(text, lex)
    return out


def _humanize(text):
    hz = load("humanize")
    _, report = hz.humanize(text, hz.load_lexicon())
    # The typographic pass straightens "’" by design and reports it.
    return {"lexical": report["lexical"], "structures": report["structures"]}


def _swipe(text):
    sw = load("swipe")
    return sw.classify(text, sw.load_formulas(sw.HOOKS))


# What each tool answers for a piece of text, through its public entry point.
ENTRY = {
    "hookscore": lambda t: load("hookscore").run(t),
    "beats": lambda t: load("beats").analyse(t),
    "caption": lambda t: load("caption").analyse(t),
    "humanize": _humanize,
    "detect": _detect,
    "swipe": _swipe,
}


class ApostropheNet(unittest.TestCase):
    def test_every_tool_has_an_entry(self):
        self.assertEqual(sorted(ENTRY), sorted(TOOLS))

    def test_every_apostrophe_key_is_known(self):
        stray = sorted({(f, k) for f, k, v in data_strings()
                        if "'" in v and k not in MATCH_KEYS and k not in DISPLAY_KEYS})
        self.assertEqual(stray, [], "a \"'\" under a key the net does not classify")

    def test_display_keys_are_live(self):
        used = {k for _, k, v in data_strings() if "'" in v}
        self.assertEqual(sorted(set(DISPLAY_KEYS) - used), [], "dead exemption")

    def test_redundant_exemptions_are_live(self):
        for value in REDUNDANT:
            with self.subTest(value=value):
                self.assertIn(value, [v for _, _, v in members()], "dead exemption")
                pat = re.compile(value, re.IGNORECASE)
                hits = [w for w in WITNESSES + ["You're up next."]
                        if pat.search(w)]
                self.assertTrue(hits)
                self.assertTrue(all(pat.search(curly(w)) for w in hits), "not redundant")

    def test_every_member_has_a_witness_and_a_reader(self):
        found = members()
        self.assertGreater(len(found), 30)  # the scan reached the data
        orphans = [(f, k, v[:50]) for f, k, v in found
                   if v not in REDUNDANT and not witnesses_for(k, v)]
        self.assertEqual(orphans, [], "regex with \"'\" that no witness exercises")
        unread = sorted({f for f, _, _ in found if not readers(f)})
        self.assertEqual(unread, [], "data no tool reads")

    def test_curly_apostrophe_answers_like_the_straight_one(self):
        bad = []
        for f, k, v in members():
            for tool in readers(f):
                for w in witnesses_for(k, v):
                    if canon(ENTRY[tool](w)) != canon(ENTRY[tool](curly(w))):
                        bad.append((tool, k, v[:40], w))
        self.assertEqual(bad, [])


class Normalisation(unittest.TestCase):
    # humanize is the one tool without the constant: its typographic pass
    # rewrites "’" to "'" before anything is matched (test below).
    NO_CONSTANT = {"humanize": "the typographic pass straightens quotes first"}

    def test_one_identical_constant_per_tool(self):
        line = 'APOSTROPHES = str.maketrans("‘’", "\'\'")'
        for name, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            with self.subTest(tool=name):
                want = 0 if name in self.NO_CONSTANT else 1
                self.assertEqual(src.count(line), want)
                self.assertEqual(src.count("APOSTROPHES ="), want)

    def test_humanize_straightens_both_single_quotes(self):
        # humanize matches after its typographic pass: that pass is its
        # normalisation point, so the data has to keep mapping both quotes.
        lex = load("humanize").load_lexicon()
        typo = {e["from"]: e["to"] for e in lex["typographic"]}
        self.assertEqual(typo.get("’"), "'")
        self.assertEqual(typo.get("‘"), "'")

    def test_left_quote_used_as_apostrophe(self):
        hs = load("hookscore")
        self.assertEqual(hs.run("What‘s up guys, here is the plan.")[3],
                         hs.run("What's up guys, here is the plan.")[3])

    def test_user_text_is_not_rewritten(self):
        a = load("caption").analyse("Don’t miss the 3 rules.")
        self.assertIn("Don’t", a["visible"])
        b = load("beats").analyse("Don’t miss the 3 rules.")
        self.assertIn("Don’t", b["beats"][0]["text"])

    def test_caption_keywords_either_way_shown_as_typed(self):
        cp = load("caption")
        a = cp.analyse("Don’t price by the hour. 3 rules inside.", keywords=["don't price"])
        self.assertIn("1/1 present", [c for c in a["checks"] if c["check"] == "SEARCH TERMS"][0]["detail"])
        b = cp.analyse("Price by the hour. 3 rules inside.", keywords=["don’t price"])
        self.assertIn("Missing: don’t price", [c for c in b["checks"] if c["check"] == "SEARCH TERMS"][0]["detail"])

    def test_cli_greeting_typed_on_a_phone(self):
        from _support import run_tool
        r = run_tool("hookscore", "--hook", "What’s up, guys", "--json")
        self.assertIn("Greeting", r.stdout)


if __name__ == "__main__":
    unittest.main()
