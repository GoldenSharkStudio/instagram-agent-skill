"""A broken lexicon is refused at load, naming the field: never a traceback
halfway through a run, never a check skipped in silence.

slop.<lang>.json is meant to be edited by hand (`--lexicon`). A structural
tell whose regex did not compile used to vanish (`except re.error: continue`),
and detect went up to PASS on a draft that should stop at REVIEW. Other broken
fields crashed with a traceback and exit 1, which detect also uses for "not
PASS". The contract (CLAUDE.md): a lexicon that does not load is exit 2 naming
the path.

The net:
- every position of every shipped slop.*.json (each key, at each depth, list
  items taken once per shape) is broken three ways (wrong type, missing,
  a regex that does not compile under a regex key) and both loaders must
  refuse it. A position read by no tool, or a key a tool reads as optional,
  is declared below with its reason;
- the declaration that a key is not read is checked against the tools
  themselves: they run on real drafts over a lexicon that records every key
  they touch, and touching a declared key fails;
- the loaders, and `any_of` (an empty list matches nothing), are one
  function copied in both scripts (tests/test_invariants.py)."""

import glob
import json
import os
import re
import tempfile
import unittest

from _support import FIXTURES, SKILLS, load, read_fixture, run_tool
from test_invariants import REGEX_KEYS

hz, dt = load("humanize"), load("detect")
LEXICONS = sorted(glob.glob(os.path.join(SKILLS, "ig-human", "slop.*.json")))

# Read by no tool: breaking them changes nothing. `[]` marks a list item.
NOT_READ = {
    "note": "comment for the person editing the JSON",
    "version": "the lexicon's own version string, shown to nobody",
    "inflection": "rules tests/test_inflection.py checks the entries against",
    "auto": "stopwords for --lang auto, read by auto_candidates, which skips a "
            "broken file for the vote; the normal load then reports it",
    "words[].of": "the base an inflected entry belongs to, read by the tests",
    "article.note": "comment for the person editing the JSON",
}
# Read, and allowed to be absent: deleting them is not an error.
OPTIONAL = {
    "words[].roles": "an entry with no roles has one replacement for every use",
    "words[].roles[].prev": "a role with no prev holds whatever comes before",
    "words[].roles[].next": "a role with no next holds whatever comes after",
    "article": "a language whose article does not change (pt-BR) may leave it out",
    "article.vowel": "no vowel rule: no article agrees",
    "article.forms": "no forms: no article agrees",
    "article.forms.consonant": "same",
    "article.forms.vowel": "same",
    "calibrated": "absent = true, so a lexicon you wrote keeps passing",
    "lang": "absent: detect names the language it was asked for",
}

# A key REGEX_KEYS names, holding a literal here.
LITERAL_UNDER_REGEX_KEY = {
    "article.forms.vowel": "the article itself (\"an\"), written out, never matched",
}


def jload(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def positions(data):
    """(path, key-path) for each key at each depth. A list of objects gives
    each of its keys once, from the first item that has it; a list of
    strings gives its first item. `path` is a list of keys and indices."""
    out, seen = [], set()

    def walk(node, path, shape):
        if isinstance(node, dict):
            for k, v in node.items():
                s = f"{shape}.{k}" if shape else k
                if s not in seen:
                    seen.add(s)
                    out.append((path + [k], s))
                walk(v, path + [k], s)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [i], shape + "[]")
            if node and not isinstance(node[0], (dict, list)) and shape + "[]" not in seen:
                seen.add(shape + "[]")
                out.append((path + [0], shape + "[]"))
    walk(data, [], "")
    return out


def declared(shape, table):
    """The declaration covering `shape`, its own or a parent's."""
    parts = shape.split(".")
    for n in range(len(parts), 0, -1):
        if ".".join(parts[:n]) in table:
            return ".".join(parts[:n])
    return None


def wrong_type(value):
    if isinstance(value, bool):
        return "yes"
    if isinstance(value, str):
        return 7
    if isinstance(value, list):
        return "x"
    if isinstance(value, dict):
        return ["x"]
    return 7               # None (a role that keeps the word)


def breakages(data):
    """(shape, how, broken copy) for every position."""
    for path, shape in positions(data):
        parent = data
        for k in path[:-1]:
            parent = parent[k]
        value = parent[path[-1]]
        cases = [("wrong type", wrong_type(value))]
        if (isinstance(value, str) and value and path[-1] in REGEX_KEYS
                and shape not in LITERAL_UNDER_REGEX_KEY):
            cases.append(("bad regex", "(unclosed"))
        if isinstance(value, str) and shape.endswith("[]"):
            cases.append(("empty", ""))
        for how, new in cases + [("missing", None)]:
            if how == "missing" and not isinstance(parent, dict):
                continue
            copy = json.loads(json.dumps(data))
            node = copy
            for k in path[:-1]:
                node = node[k]
            if how == "missing":
                del node[path[-1]]
            else:
                node[path[-1]] = new
            yield shape, how, copy


class EveryBrokenFieldIsRefused(unittest.TestCase):
    def test_every_position_breaks_the_load(self):
        bad, ran = [], 0
        with tempfile.TemporaryDirectory() as d:
            for lexicon in LEXICONS:
                name = os.path.basename(lexicon)
                for shape, how, copy in breakages(jload(lexicon)):
                    if declared(shape, NOT_READ):
                        continue
                    if how == "missing" and declared(shape, OPTIONAL):
                        continue
                    path = os.path.join(d, "broken.json")
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(copy, fh)
                    ran += 1
                    for tool in (hz, dt):
                        try:
                            tool.load_lexicon(path)
                        except tool.LexiconError as err:
                            if path not in str(err):
                                bad.append(f"{name} {shape} {how}: {tool.__name__} did not name the file")
                        except Exception as err:          # a crash is not a refusal
                            bad.append(f"{name} {shape} {how}: {tool.__name__} crashed, "
                                       f"{type(err).__name__}: {err}")
                        else:
                            bad.append(f"{name} {shape} {how}: {tool.__name__} loaded it")
        self.assertGreater(ran, 100)          # the walk reached the data
        self.assertEqual(bad, [], f"{len(bad)} broken lexicon(s) not refused:\n" + "\n".join(bad[:60]))

    def test_declarations_are_alive(self):
        shapes = {s for p in LEXICONS for _, s in positions(jload(p))}
        for table in (NOT_READ, OPTIONAL, LITERAL_UNDER_REGEX_KEY):
            for key in table:
                self.assertIn(key, shapes, f"declared {key!r} is in no slop.*.json")


class Recorder(dict):
    """A lexicon object that writes down every key a tool touches."""
    seen = set()

    def __init__(self, data, shape):
        super().__init__({k: wrap(v, f"{shape}.{k}" if shape else k) for k, v in data.items()})
        self.shape = shape

    def _note(self, key):
        Recorder.seen.add(f"{self.shape}.{key}" if self.shape else key)

    def __getitem__(self, key):
        self._note(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._note(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._note(key)
        return super().__contains__(key)


def wrap(value, shape):
    if isinstance(value, dict):
        return Recorder(value, shape)
    if isinstance(value, list):
        return [wrap(v, shape + "[]") for v in value]
    return value


def drafts(data):
    """Real drafts, plus one character of every invisible and typographic
    entry, so every pass reaches every section."""
    texts = [read_fixture("bad_draft.txt"), read_fixture("good_draft.txt"),
             "Follow for more if you love design.\nIt is crucial — also, it's proof.\n"
             "I'm thrilled to share that we hit 10k. Today and follow for more.\n"]
    uses = os.path.join(FIXTURES, f"lexicon_uses.{data.get('lang', 'en')}.json")
    if os.path.exists(uses):
        texts += [u["text"] for u in jload(uses)["uses"]]
    marks = []
    for e in data["invisible"]:
        start = e["cp"].split("-")[0]
        marks.append(chr(int(start[2:], 16)))
    marks += [e["from"] for e in data["typographic"]]
    texts.append("Hi" + " x ".join(marks) + " there.")
    return texts


class NotReadMeansNotRead(unittest.TestCase):
    def test_no_tool_touches_a_declared_key(self):
        touched = set()
        for lexicon in LEXICONS:
            data = jload(lexicon)
            lang = data.get("lang", "en")
            Recorder.seen = set()
            lex = wrap(data, "")
            for text in drafts(data):
                hz.humanize(text, lex, lang)
                dt.run(text, lex, lang)
            touched |= Recorder.seen
        self.assertGreater(len(touched), 20)
        wrong = sorted(s for s in touched if declared(s, NOT_READ))
        self.assertEqual(wrong, [], "declared not read, but a tool reads it")


class TheBrokenRegexThatPassed(unittest.TestCase):
    """AUD-003 as it was found: one tell's regex broken, a draft with that tell."""

    def test_exit_two_naming_the_file(self):
        draft = read_fixture("good_draft.txt") + "It's not just a tool, it's a habit.\n"
        data = jload(os.path.join(SKILLS, "ig-human", "slop.en.json"))
        data["structures"][0]["regex"] = "(unclosed"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "slop.mine.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            for tool in ("detect", "humanize"):
                with self.subTest(tool=tool):
                    r = run_tool(tool, "-", "--lexicon", path, stdin=draft)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(path, r.stderr)
                    self.assertIn("structures[0].regex", r.stderr)
                    self.assertNotIn("Traceback", r.stderr)


class ValuesTheWalkDoesNotMake(unittest.TestCase):
    """Broken values of the right type, which the walk above never writes."""

    def test_refused(self):
        cases = [("invisible", 0, "cp", "U+200D-U+200B"), ("invisible", 0, "cp", "U+110000"),
                 ("invisible", 0, "cp", "200B"), ("invisible", 0, "action", "erase"),
                 ("words", 0, "find", ""), ("typographic", 0, "from", "")]
        with tempfile.TemporaryDirectory() as d:
            for section, i, key, value in cases:
                data = jload(os.path.join(SKILLS, "ig-human", "slop.en.json"))
                data[section][i][key] = value
                path = os.path.join(d, "broken.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                for tool in (hz, dt):
                    with self.subTest(tool=tool.__name__, field=f"{section}[{i}].{key}", value=value):
                        with self.assertRaises(tool.LexiconError) as cm:
                            tool.load_lexicon(path)
                        self.assertIn(f"{section}[{i}].{key}", str(cm.exception))


class AnEmptyListMatchesNothing(unittest.TestCase):
    """An empty list in the lexicon is a language with no such words, not a
    pattern that matches everywhere."""

    def lex(self, **lists):
        lex = hz.load_lexicon(lang="en")
        lex = json.loads(json.dumps(lex))
        lex.update(lists)
        return lex

    def test_any_of_an_empty_list_never_matches(self):
        for tool in (hz, dt):
            self.assertIsNone(re.search(tool.any_of([]), "anything at all"))
            self.assertEqual(tool.any_of(["a.b"]), re.escape("a.b"))

    def test_no_dependents_holds_nothing(self):
        got, _ = hz.humanize("Buckle up the ride is long.\n", self.lex(dependents=[]), "en")
        self.assertNotIn("uckle", got)
        self.assertEqual(dt.count_hanging("Buckle up the ride is long.", self.lex(dependents=[])), 0)

    def test_every_list_can_be_empty(self):
        for key in ("connectives", "conjunctions", "dependents", "complementizers"):
            with self.subTest(key=key):
                lex = self.lex(**{key: []})
                for text in drafts(lex):
                    hz.humanize(text, lex, "en")
                    dt.run(text, lex, "en")

    def test_no_connectives_and_a_dash(self):
        got, _ = hz.humanize("It is crucial — also, it's proof.\n", self.lex(connectives=[]), "en")
        self.assertNotIn("—", got)


if __name__ == "__main__":
    unittest.main()
