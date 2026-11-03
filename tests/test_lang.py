"""Language data lives in JSON, not in Python (fase 2, passo 1).

The net is derived from the source: every string handed to a `re.*` call and
every literal collection of words in the six scripts is scanned, so a lexicon
added later in code fails here without anyone remembering to list it. Then,
per tool, the JSON is proven to be the source (edit it in a lone copy, the
output moves) and a missing or broken file fails closed with exit 2, never
with a traceback that a skill would read as a verdict.
"""

import ast
import json
import os
import re
import shutil
import tempfile
import unittest

from _support import SKILLS, TOOLS, fixture, run_tool

# The data file each tool reads its language from, relative to its folder.
LANG_FILE = {
    "hookscore": os.path.join("lang", "en.json"),
    "beats": os.path.join("lang", "en.json"),
    "caption": os.path.join("lang", "en.json"),
    "humanize": "slop.en.json",
    "detect": "slop.en.json",
}

# Strings that look like word lists but are not language. Keyed by a
# substring of the regex; each one says why.
NOT_LANGUAGE = {
    r"(?:com|co|io|net|org|ai|app)": "top-level domains, the same in every language",
}

def _schema_keys():
    """Every key name in the data files. A tuple of these in code is the
    script reading its JSON, not a word list."""
    keys = set()

    def walk(x):
        if isinstance(x, dict):
            keys.update(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for tool, rel in LANG_FILE.items():
        with open(os.path.join(os.path.dirname(TOOLS[tool]), rel), encoding="utf-8") as fh:
            walk(json.load(fh))
    return keys


SCHEMA_KEYS = _schema_keys()
RE_CALLS = {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub", "split"}
WORDISH = re.compile(r"^#?[a-z][a-z'’ ]*$")


def _regex_words(pattern):
    """Lowercase words of 2+ letters left in a regex once escapes and inline
    flags are gone. `\\bhours?\\b` -> ['hours']."""
    bare = re.sub(r"\\[A-Za-z]|\(\?[a-zA-Z]+\)|\(\?[:=!<]+", " ", pattern)
    return set(re.findall(r"[a-z]{2,}", bare))


def hardcoded_lexicons(path):
    """(line, kind, sample) for every language-looking literal in a script."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            strs = [e.value for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(strs) >= 5 and set(strs) <= SCHEMA_KEYS:
                continue
            if len(strs) >= 5 and sum(bool(WORDISH.match(s)) for s in strs) >= 5:
                found.append((node.lineno, "word list", strs[:4]))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in RE_CALLS
              and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
              and node.args and isinstance(node.args[0], (ast.Constant, ast.JoinedStr,
                                                          ast.BinOp))):
            parts = [n.value for n in ast.walk(node.args[0])
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            pattern = "".join(parts)
            if any(k in pattern for k in NOT_LANGUAGE):
                continue
            words = _regex_words(pattern)
            if len(words) >= 3:
                found.append((node.lineno, "regex", sorted(words)[:4]))
    return found


class NoLexiconInCode(unittest.TestCase):
    def test_scanner_sees_a_planted_lexicon(self):
        # The guard is only worth something if it can fail.
        src = ('import re\nW = {"alpha", "bravo", "charlie", "delta", "echo"}\n'
               'R = re.compile(r"\\b(?:never|always|stop)\\b")\n'
               'U = re.compile(r"(?:%|k\\b|hrs?\\b|hours?\\b|days?\\b)")\n')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "planted.py")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src)
            kinds = [k for _, k, _ in hardcoded_lexicons(p)]
        self.assertEqual(kinds.count("word list"), 1)
        self.assertEqual(kinds.count("regex"), 2)

    def test_scripts_carry_no_lexicon(self):
        for name, path in TOOLS.items():
            with self.subTest(tool=name):
                self.assertEqual(hardcoded_lexicons(path), [],
                                 f"{name}: language data belongs in its JSON")


def lone_copy(d, tool):
    """Copy the tool's folder into d, return (script path, lang file path)."""
    folder = os.path.basename(os.path.dirname(TOOLS[tool]))
    dest = os.path.join(d, folder)
    shutil.copytree(os.path.join(SKILLS, folder), dest,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return (os.path.join(dest, os.path.basename(TOOLS[tool])),
            os.path.join(dest, LANG_FILE.get(tool, "")))


def edit_json(path, change):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    change(data)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


# Minimal valid input for each tool, to see the file load or fail.
INPUT = {
    "hookscore": ("-", "I lost $18,000 because of one missing contract.\n"),
    "beats": ("-", "I lost $18,000 on one contract.\nHere is the clause.\n"),
    "caption": ("-", "I lost $18,000 on one contract. Save this.\n"),
    "humanize": ("-", "A crucial point.\n"),
    "detect": (fixture("good_draft.txt"), None),
}


class JsonIsTheSource(unittest.TestCase):
    def run_copy(self, tool, change, *args, stdin=None):
        with tempfile.TemporaryDirectory() as d:
            script, lang = lone_copy(d, tool)
            edit_json(lang, change)
            return run_tool(script, *args, stdin=stdin)

    def test_hookscore_stakes(self):
        hook = "A banana contract clause\n"
        # One hook in, one object out (a batch gives a list).
        before = json.loads(run_tool("hookscore", "-", "--json", stdin=hook).stdout)
        proc = self.run_copy("hookscore", lambda j: j["hookscore"]["stakes"].append("banana"),
                             "-", "--json", stdin=hook)
        after = json.loads(proc.stdout)
        self.assertNotIn("banana", before["checks"]["STAKES"]["detail"])
        self.assertIn("banana", after["checks"]["STAKES"]["detail"])

    def test_hookscore_dealbreaker(self):
        def add(j):
            j["hookscore"]["dealbreakers"].append(
                {"regex": "(?i)\\bbanana\\b", "message": "Banana in the hook."})
        proc = self.run_copy("hookscore", add, "--hook", "Steal this banana clause", "--json")
        self.assertIn("Banana in the hook.", json.loads(proc.stdout)["flags"])

    def test_beats_stopwords(self):
        script = "Contract is the trap.\nRead the contract.\n"
        base = run_tool("beats", "-", "--target", "30", "--json", stdin=script)
        self.assertIn("contract", json.dumps(json.loads(base.stdout)["notes"]).lower())
        proc = self.run_copy("beats", lambda j: j["beats"]["stopwords"].append("contract"),
                             "-", "--target", "30", "--json", stdin=script)
        self.assertIn("No loop", json.dumps(json.loads(proc.stdout)["notes"]))

    def test_caption_filler_tags(self):
        cap = "I lost $18,000 on one contract. Save this.\n\n#banana\n"
        proc = self.run_copy("caption", lambda j: j["caption"]["filler_tags"].append("#banana"),
                             "-", "--json", stdin=cap)
        hashtags = [c for c in json.loads(proc.stdout)["checks"] if c["check"] == "HASHTAGS"]
        self.assertIn("#banana", hashtags[0]["detail"])

    def test_caption_asks(self):
        cap = "I lost $18,000 on one contract. Banana me.\n"
        def add(j):
            j["caption"]["asks"].append({"id": "banana", "regex": "(?i)\\bbanana me\\b",
                                         "name": "banana"})
        proc = self.run_copy("caption", add, "-", "--json", stdin=cap)
        self.assertEqual(json.loads(proc.stdout)["asks"], ["banana"])
        self.assertEqual(json.loads(proc.stdout)["ask_ids"], ["banana"])

    def test_caption_ask_without_id_fails_closed(self):
        # ask_ids is a contract: an ask with no id is a broken file, not a guess.
        def add(j):
            j["caption"]["asks"].append({"regex": "(?i)\\bbanana me\\b", "name": "banana"})
        proc = self.run_copy("caption", add, "-", "--json", stdin="Banana me.\n")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("en.json", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_detect_pronouns(self):
        args = (fixture("good_draft.txt"), "--json")
        base = json.loads(run_tool("detect", *args).stdout)["checks"]["VOICE"]["detail"]
        proc = self.run_copy("detect", lambda j: j["voice"].update(pronouns="\\bzzzz\\b"), *args)
        after = json.loads(proc.stdout)["checks"]["VOICE"]["detail"]
        self.assertNotIn(" 0.0 personal pronouns", base)
        self.assertIn(" 0.0 personal pronouns", after)

    def test_detect_contractions(self):
        args = (fixture("good_draft.txt"), "--json")
        proc = self.run_copy("detect", lambda j: j["voice"].update(contractions="\\bzzzz\\b"),
                             *args)
        detail = json.loads(proc.stdout)["checks"]["VOICE"]["detail"]
        self.assertTrue(detail.startswith("0.0 contractions"), detail)


class MissingDataFailsClosed(unittest.TestCase):
    def check(self, tool, breaker):
        arg, stdin = INPUT[tool]
        with tempfile.TemporaryDirectory() as d:
            script, lang = lone_copy(d, tool)
            breaker(lang)
            proc = run_tool(script, arg, stdin=stdin)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(os.path.basename(lang), proc.stderr)

    def test_missing_file(self):
        for tool in LANG_FILE:
            with self.subTest(tool=tool):
                self.check(tool, os.remove)

    def test_broken_json(self):
        def corrupt(p):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("{ not json")
        for tool in LANG_FILE:
            with self.subTest(tool=tool):
                self.check(tool, corrupt)

    def test_missing_key(self):
        drop = {
            "hookscore": lambda j: j["hookscore"].pop("stakes"),
            "beats": lambda j: j["beats"].pop("stopwords"),
            "caption": lambda j: j["caption"].pop("asks"),
            "humanize": lambda j: j.pop("words"),
            "detect": lambda j: j["voice"].pop("pronouns"),
        }
        for tool, change in drop.items():
            with self.subTest(tool=tool):
                self.check(tool, lambda p, c=change: edit_json(p, c))

    def test_missing_hanging_clause_keys(self):
        # The keys the hanging-deletion rule reads (03/11): without them the
        # rule cannot run, and silently deleting again would be failing open.
        drop = (("humanize", "dependents"), ("humanize", "complementizers"),
                ("detect", "dependents"))
        for tool, key in drop:
            with self.subTest(tool=tool, key=key):
                self.check(tool, lambda p, k=key: edit_json(p, lambda j: j.pop(k)))

    def test_bad_regex(self):
        def bad(j):
            j["hookscore"]["dealbreakers"][0]["regex"] = "(unclosed"
        self.check("hookscore", lambda p: edit_json(p, bad))

    def test_missing_messages_key(self):
        # Every sentence a tool prints comes from "messages" in its language
        # file: without the key there is no language to say it in.
        for tool, section in (("hookscore", "hookscore"), ("beats", "beats"),
                              ("caption", "caption")):
            with self.subTest(tool=tool):
                self.check(tool, lambda p, s=section: edit_json(p, lambda j: j[s].pop("messages")))

    def test_messages_that_are_not_strings(self):
        def number(section):
            def change(j):
                key = next(iter(j[section]["messages"]))
                j[section]["messages"][key] = 7
            return change
        for tool, section in (("hookscore", "hookscore"), ("beats", "beats"),
                              ("caption", "caption")):
            with self.subTest(tool=tool):
                self.check(tool, lambda p, c=number(section): edit_json(p, c))

    def test_swipe_degrades_when_hookscore_cannot_load(self):
        with tempfile.TemporaryDirectory() as d:
            for folder in ("ig-viral", "ig-reel"):
                shutil.copytree(os.path.join(SKILLS, folder), os.path.join(d, folder),
                                ignore=shutil.ignore_patterns("__pycache__"))
            os.remove(os.path.join(d, "ig-reel", "lang", "en.json"))
            proc = run_tool(os.path.join(d, "ig-viral", "swipe.py"),
                            fixture("captured.tsv"), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("hookscore.py not importable", proc.stderr)
        self.assertTrue(all(r["hook_score"] is None for r in json.loads(proc.stdout)["reels"]))


# Where the messages of the tools that keep them apart from their lexicon live.
MESSAGES_FILE = {
    "humanize": ("lang/en.json", "humanize"),
    "detect": ("lang/en.json", "detect"),
    "swipe": ("lang/en.json", "swipe"),
}
MESSAGES_INPUT = dict(INPUT, swipe=(fixture("captured.tsv"), None))


class MissingMessagesFailClosed(unittest.TestCase):
    """ig-human and ig-viral read their sentences from their own lang/en.json,
    never from the lexicon: a lost file is exit 2 naming it, not a traceback."""

    def check(self, tool, breaker):
        arg, stdin = MESSAGES_INPUT[tool]
        with tempfile.TemporaryDirectory() as d:
            script, _ = lone_copy(d, tool)
            path = os.path.join(os.path.dirname(script), MESSAGES_FILE[tool][0])
            breaker(path)
            proc = run_tool(script, arg, stdin=stdin)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(path, proc.stderr)

    def test_missing_file(self):
        for tool in MESSAGES_FILE:
            with self.subTest(tool=tool):
                self.check(tool, os.remove)

    def test_broken_json(self):
        def corrupt(p):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("{ not json")
        for tool in MESSAGES_FILE:
            with self.subTest(tool=tool):
                self.check(tool, corrupt)

    def test_missing_messages_key(self):
        for tool, (_, section) in MESSAGES_FILE.items():
            with self.subTest(tool=tool):
                self.check(tool, lambda p, s=section: edit_json(p, lambda j: j[s].pop("messages")))

    def test_message_that_is_not_a_string(self):
        def number(section):
            def change(j):
                key = next(iter(j[section]["messages"]))
                j[section]["messages"][key] = 7
            return change
        for tool, (_, section) in MESSAGES_FILE.items():
            with self.subTest(tool=tool):
                self.check(tool, lambda p, c=number(section): edit_json(p, c))


if __name__ == "__main__":
    unittest.main()
