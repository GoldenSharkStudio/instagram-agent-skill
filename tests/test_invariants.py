"""Invariants the repo promises in prose. Adding an entry to a JSON without
updating the numbers quoted in README/SKILL.md/plugin.json fails here."""

import ast
import glob
import json
import os
import re
import sys
import unittest

from _support import ROOT, SKILLS, TOOLS, load

WORD_NUMBERS = {"five": 5, "twelve": 12, "thirteen": 13, "fourteen": 14, "sixteen": 16, "eighteen": 18,
                "twenty-six": 26}


def jload(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


SLOP = jload("skills", "ig-human", "slop.en.json")
HOOKS = jload("skills", "ig-reel", "hooks.json")
RUBRIC = jload("skills", "ig-profile", "rubric.json")
SKILL_DIRS = sorted(d for d in glob.glob(os.path.join(SKILLS, "ig-*")) if os.path.isdir(d))

PROSE_FILES = (["README.md", "CLAUDE.md", ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json"]
               + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))])


def prose(path):
    """File text without fenced code blocks: those are sample tool output,
    where "9 structural tells" describes a draft, not the lexicon. The one
    exception is the README "## Files" listing, which states counts."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        text = fh.read()
    keep = re.search(r"## Files\n\n```.*?```", text, flags=re.S)
    stripped = re.sub(r"```.*?```", "", text, flags=re.S)
    return stripped + ("\n" + keep.group(0) if keep else "")


def claims(pattern):
    """Every (file, number) the prose states for `pattern` (one group).
    Whitespace is collapsed first: Markdown wraps at any space, so "the same
    26\\nformulas" is a claim too, and a literal space in `pattern` missed it."""
    found = []
    for path in PROSE_FILES:
        for m in re.finditer(pattern, re.sub(r"\s+", " ", prose(path)), re.IGNORECASE):
            raw = m.group(1).lower()
            found.append((path, int(raw) if raw.isdigit() else WORD_NUMBERS[raw]))
    return found


NUM = r"(\d+|" + "|".join(WORD_NUMBERS) + r")"


class CountsInProse(unittest.TestCase):
    def assertClaims(self, pattern, expected, at_least=1):
        found = claims(pattern)
        self.assertGreaterEqual(len(found), at_least, f"no mention of {pattern!r}")
        wrong = [(p, n) for p, n in found if n != expected]
        self.assertEqual(wrong, [], f"prose says something other than {expected}")

    def test_lexicon_terms(self):
        self.assertClaims(NUM + r" (?:stock words|terms)\b", len(SLOP["words"]) + len(SLOP["phrases"]), 3)

    def test_invisible_classes(self):
        self.assertClaims(NUM + r" invisible\b", len(SLOP["invisible"]), 3)

    def test_typographic_substitutions(self):
        self.assertClaims(NUM + r" typographic substitutions", len(SLOP["typographic"]))

    def test_structural_tells(self):
        self.assertClaims(NUM + r" (?:structural )?tells\b", len(SLOP["structures"]), 2)

    def test_hook_formulas(self):
        self.assertClaims(NUM + r" (?:hook )?formulas", len(HOOKS["hooks"]), 4)

    def test_skill_count(self):
        self.assertClaims(NUM + r" (?:claude )?skills\b", len(SKILL_DIRS), 4)
        self.assertIn("## The fourteen", prose("README.md"))
        self.assertEqual(len(SKILL_DIRS), 14)

    def test_readme_table_lists_every_skill(self):
        """One row per skill folder, in the table under "## The fourteen"."""
        table = re.search(r"## The fourteen\n\n(.*?)\n\n", prose("README.md"), re.S).group(1)
        rows = re.findall(r"^\| `/(ig-[a-z]+)` \|", table, re.M)
        self.assertEqual(sorted(rows), [os.path.basename(d) for d in SKILL_DIRS])

    def test_rubric(self):
        self.assertClaims(NUM + r"-part rubric", len(RUBRIC["items"]), 2)
        self.assertEqual(sum(i["points"] for i in RUBRIC["items"]), RUBRIC["total"])
        self.assertEqual(RUBRIC["total"], 100)

    def test_hashtag_cap_in_prose_matches_code(self):
        cap = load("caption").HASHTAG_LIMIT
        word = {v: k for k, v in WORD_NUMBERS.items()}[cap]
        self.assertIn(f"**{word} per post**", prose("README.md"))


class HooksJson(unittest.TestCase):
    FIELDS = ["id", "name", "template", "example", "on_screen", "best_for", "trap", "match"]

    def test_ids_and_order(self):
        ids = [h["id"] for h in HOOKS["hooks"]]
        self.assertEqual(sorted(ids), list(range(1, len(ids) + 1)))
        self.assertEqual(sorted(HOOKS["classify_order"]), sorted(ids))
        names = [h["name"] for h in HOOKS["hooks"]]
        self.assertEqual(len(set(names)), len(names))

    def test_every_field_present(self):
        for h in HOOKS["hooks"]:
            for f in self.FIELDS:
                with self.subTest(id=h["id"], field=f):
                    self.assertTrue(str(h.get(f, "")).strip())

    def test_every_match_compiles(self):
        # Per language since 4a.2; tests/test_hooks_lang.py owns the schema.
        for h in HOOKS["hooks"]:
            for code, rx in h["match"].items():
                with self.subTest(id=h["id"], lang=code):
                    re.compile(rx, re.IGNORECASE)

    def test_examples_never_misfire_into_another_formula(self):
        sw = load("swipe")
        formulas = sw.load_formulas(os.path.join(SKILLS, "ig-reel", "hooks.json"))
        own = 0
        for h in HOOKS["hooks"]:
            fid, _ = sw.classify(h["example"], formulas)
            with self.subTest(id=h["id"], got=fid):
                self.assertIn(fid, (h["id"], None))
            own += fid == h["id"]
        # Regression floor measured on 05/11/2026: 24 of 30 examples name
        # their own formula (20 of 26 on 02/11, plus the four new ones).
        # Changing a match regex must not lower it.
        self.assertGreaterEqual(own, 24)


class SlopJson(unittest.TestCase):
    def test_structure_regexes_compile(self):
        # Both tools skip a structure whose regex fails to compile, silently.
        # That guard fails open, so the data has to be right.
        for s in SLOP["structures"]:
            with self.subTest(id=s["id"]):
                re.compile(s["regex"], re.MULTILINE)
                self.assertTrue(s["name"] and s["fix"])

    def test_lexicon_entries(self):
        finds = []
        for e in SLOP["words"] + SLOP["phrases"]:
            with self.subTest(find=e.get("find")):
                # `of` names the base of an inflected form (tests/test_inflection.py)
                self.assertIn(set(e), ({"find", "replace", "family"},
                                       {"find", "replace", "family", "of"}))
                self.assertTrue(e["find"].strip())
            finds.append(e["find"].lower())
        dupes = sorted({f for f in finds if finds.count(f) > 1})
        self.assertEqual(dupes, [])

    def test_invisible_codepoints(self):
        for e in SLOP["invisible"]:
            with self.subTest(cp=e["cp"]):
                self.assertRegex(e["cp"], r"^U\+[0-9A-F]{4,5}(?:-U\+[0-9A-F]{4,5})?$")
                self.assertIn(e["action"], {"delete", "space"})

    def test_typographic_entries(self):
        for e in SLOP["typographic"]:
            with self.subTest(name=e.get("name")):
                self.assertEqual(len(e["from"]), 1)
                self.assertIn("to", e)


def script_paths():
    """Every tool script, read from the tree (not from the TOOLS registry)."""
    return sorted(p for p in glob.glob(os.path.join(SKILLS, "*", "*.py"))
                  if not os.path.basename(p).startswith("_"))


def module_regexes():
    """{NAME_RE: {tool: (pattern, flags source)}} for every module-level
    `NAME_RE = re.compile("literal", ...)` in every script, parsed from src."""
    by_path = {os.path.realpath(p): n for n, p in TOOLS.items()}
    out = {}
    for path in script_paths():
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.endswith("_RE")
                    and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "re.compile"):
                continue
            pattern = ast.literal_eval(node.value.args[0])
            flags = " ".join(ast.unparse(a) for a in node.value.args[1:])
            tool = by_path.get(os.path.realpath(path), os.path.relpath(path, ROOT))
            out.setdefault(node.targets[0].id, {})[tool] = (pattern, flags)
    return out


# Same name, different regex, on purpose. Each entry says why; anything not
# listed here must be byte-identical in every script that defines the name.
DRIFT_ALLOWED = {
    ("SENT_RE", "beats"): "beats splits the script into lines before sentences, "
                          "so it has no newline to exclude; the result is the same",
    ("WORD_RE", "detect"): "detect counts words for voice and slop: letters and "
                           "apostrophes only, no digits, $ or % (test_unicode keeps "
                           "both shapes Unicode)",
}


class DuplicatedRegexes(unittest.TestCase):
    """Copied on purpose so each folder stands alone. Copies must not drift."""

    def test_tools_registry_covers_every_script(self):
        # Every net that loops over TOOLS is blind to a script missing here.
        registered = {os.path.realpath(p) for p in TOOLS.values()}
        missing = [os.path.relpath(p, ROOT) for p in script_paths()
                   if os.path.realpath(p) not in registered]
        self.assertEqual(missing, [], "add these to TOOLS in tests/_support.py")

    def test_same_name_same_regex(self):
        regexes = module_regexes()
        self.assertIn("EMOJI_RE", regexes)  # the parser still sees the copies
        drift = {}
        for name, copies in regexes.items():
            kept = {t: v for t, v in copies.items() if (name, t) not in DRIFT_ALLOWED}
            if len(set(kept.values())) > 1:
                drift[name] = kept
        self.assertEqual(drift, {})

    def test_drift_allowances_are_live(self):
        # An allowance for a copy that no longer differs (or no longer exists)
        # is a hole waiting for the next real drift: remove it.
        regexes = module_regexes()
        for (name, tool), why in DRIFT_ALLOWED.items():
            with self.subTest(name=name, tool=tool):
                copies = regexes.get(name, {})
                self.assertIn(tool, copies)
                others = {v for t, v in copies.items() if t != tool}
                self.assertTrue(others and copies[tool] not in others, why)

    def test_lexicon_term_re(self):
        # humanize replaces what detect counts: same regex for every entry.
        hz, dt = load("humanize"), load("detect")
        drift = [e["find"] for e in SLOP["words"] + SLOP["phrases"]
                 if hz.term_re(e["find"]).pattern != dt.term_re(e["find"]).pattern]
        self.assertEqual(drift, [])

    def test_lexicon_hangs(self):
        # humanize holds back what detect counts as a hanging tell: the two
        # copies of the rule must be the same function, word for word.
        import inspect
        hz, dt = load("humanize"), load("detect")
        self.assertEqual(inspect.getsource(hz.hangs), inspect.getsource(dt.hangs))


# What a reader counts as one emoji. A copy of EMOJI_RE in any script must
# count these the same way (the scripts are found from src, not listed here).
EMOJI_CASES = [
    ("🔥", 1), ("❤️", 1), ("👍🏽", 1), ("👨‍👩‍👧", 1), ("🇧🇷", 1), ("1️⃣", 1),
    ("⭐", 1), ("✅", 1), ("☀️", 1), ("➡️", 1), ("⬇️", 1), ("↘️", 1), ("‼️", 1),
    ("🇧🇷🔥", 2), ("❤️❤️", 2), ("👩🏾‍💻 ok 🚀", 2),
    ("→", 0), ("Before → after", 0), ("™", 0), ("©", 0), ("#1 tip", 0), ("1.", 0),
    ("plain text", 0), ("“quotes” — dash…", 0),
]


class EmojiCount(unittest.TestCase):

    def test_every_copy_counts_clusters(self):
        tools = sorted(module_regexes()["EMOJI_RE"])
        self.assertGreaterEqual(len(tools), 2)
        for tool in tools:
            rx = getattr(load(tool), "EMOJI_RE")
            for text, n in EMOJI_CASES:
                with self.subTest(tool=tool, text=text):
                    self.assertEqual(len(rx.findall(text)), n)


# Keys whose string values the tools hand to re.compile. A regex-looking
# string under any other key fails RegexDataNet.test_every_regex_key_is_known,
# so a new regex field cannot dodge the net below.
REGEX_KEYS = {"regex", "match", "contractions", "pronouns", "address_me",
              "address_you", "number_units", "pattern", "cta"}
REGEX_HINTS = ("\\b", "(?", "\\s", "\\d", "[^")


# A value written once per language ({"en": ..., "pt-BR": ...}, as hooks.json
# `match`) is still the value of its own key: the language is not the key.
LANG_CODES = {c for c in load("swipe").LANGS if c != "auto"}


def data_strings():
    """(file, key, value) for every string in every JSON under skills/."""
    out = []

    def walk(obj, key, path):
        if isinstance(obj, dict):
            per_lang = bool(obj) and set(obj) <= LANG_CODES
            for k, v in obj.items():
                walk(v, key if per_lang else k, path)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key, path)
        elif isinstance(obj, str):
            out.append((path, key, obj))

    for path in sorted(glob.glob(os.path.join(SKILLS, "**", "*.json"), recursive=True)):
        with open(path, encoding="utf-8") as fh:
            walk(json.load(fh), None, os.path.relpath(path, ROOT))
    return out


def _skip_siblings(pattern, pos):
    """From a "|", return the index of the ")" closing this group, or len."""
    depth, in_class, n = 0, False, len(pattern)
    while pos < n:
        c = pattern[pos]
        if c == "\\":
            pos += 2
            continue
        if in_class:
            in_class = c != "]"
        elif c == "[":
            in_class = True
        elif c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                return pos
            depth -= 1
        pos += 1
    return n


def _tail_is_empty(pattern, pos):
    """True if nothing after `pos` can consume a character."""
    n = len(pattern)
    while pos < n:
        c = pattern[pos]
        if c == "|":
            pos = _skip_siblings(pattern, pos + 1)
        elif c == ")" or c in "?*+$":
            pos += 1
        elif pattern.startswith("\\b", pos) or pattern.startswith("\\Z", pos):
            pos += 2
        else:
            return False
    return True


def terminal_space_alternatives(pattern):
    """Alternatives that end the whole match on a literal space ("hey |hi )").
    A trailing space used as a word end misses "Hey," and "Hi!", which is how
    the greeting dealbreaker leaked. A space followed by more pattern is a
    separator between words and is fine."""
    hits, in_class, i, n = [], False, 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\":
            i += 2
            continue
        if in_class:
            in_class = c != "]"
        elif c == "[":
            in_class = True
        elif c == " " and _tail_is_empty(pattern, i + 1):
            start = max(pattern.rfind("|", 0, i), pattern.rfind("(", 0, i)) + 1
            hits.append(pattern[start:i + 1])
        i += 1
    return hits


class RegexDataNet(unittest.TestCase):
    """Class net for "trailing space as a word end" in the JSON regexes."""

    def test_detector_sees_a_planted_trailing_space(self):
        self.assertTrue(terminal_space_alternatives(r"(?i)^\s*(?:hey |hi )"))
        self.assertTrue(terminal_space_alternatives(r"\bfoo |\bbar\b"))
        self.assertFalse(terminal_space_alternatives(r"(?i)^\s*(?:hey|hi)\b"))
        self.assertFalse(terminal_space_alternatives(r"\bcomment (?:the word |\")?[A-Z]{2,}\b"))
        self.assertFalse(terminal_space_alternatives(r"\bnow (?:it )?(?:only )?takes?\b"))

    def test_every_regex_key_is_known(self):
        stray = [(f, k, v[:40]) for f, k, v in data_strings()
                 if k not in REGEX_KEYS and any(h in v for h in REGEX_HINTS)]
        self.assertEqual(stray, [], "regex-looking data under a key the net does not scan")

    def test_no_regex_ends_on_a_literal_space(self):
        regexes = [(f, k, v) for f, k, v in data_strings() if k in REGEX_KEYS]
        self.assertGreater(len(regexes), 50)  # the scan reached the data
        bad = [(f, k, hit) for f, k, v in regexes for hit in terminal_space_alternatives(v)]
        self.assertEqual(bad, [])


class Manifests(unittest.TestCase):
    def test_skill_frontmatter(self):
        for d in SKILL_DIRS:
            with self.subTest(skill=os.path.basename(d)):
                with open(os.path.join(d, "SKILL.md"), encoding="utf-8") as fh:
                    text = fh.read()
                m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
                self.assertTrue(m, "frontmatter")
                name = re.search(r"^name:\s*(.+)$", m.group(1), re.M).group(1).strip()
                self.assertEqual(name, os.path.basename(d))
                desc = m.group(1).split("description:", 1)[1].strip()
                self.assertTrue(0 < len(desc) <= 1024, len(desc))

    def test_plugin_json(self):
        p = jload(".claude-plugin", "plugin.json")
        m = jload(".claude-plugin", "marketplace.json")
        self.assertEqual(m["plugins"][0]["name"], p["name"])
        self.assertEqual(p["license"], "MIT")
        self.assertRegex(p["version"], r"^\d+\.\d+\.\d+")
        for url in (p["homepage"], p["repository"], m["plugins"][0]["homepage"]):
            self.assertIn("GoldenSharkStudio/instagram-agent-skill", url)


class StdlibOnly(unittest.TestCase):
    """The README promises no dependencies. Every import must be stdlib or a
    sibling tool from this repo."""

    LOCAL = {os.path.splitext(os.path.basename(p))[0] for p in TOOLS.values()}

    def test_imports(self):
        stdlib = set(sys.stdlib_module_names)
        for name, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods.add(node.module.split(".")[0])
            with self.subTest(tool=name):
                self.assertEqual(sorted(mods - stdlib - self.LOCAL), [])

    def test_igtools_imports(self):
        # The library front ships too, with the same promise.
        stdlib = set(sys.stdlib_module_names)
        paths = sorted(glob.glob(os.path.join(ROOT, "igtools", "*.py")))
        self.assertTrue(paths)
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods.add(node.module.split(".")[0])
            with self.subTest(file=os.path.basename(path)):
                self.assertEqual(sorted(mods - stdlib - {"igtools"}), [])


if __name__ == "__main__":
    unittest.main()


class ReadmeBlocksAreRealOutput(unittest.TestCase):
    """Key lines of the README example blocks must appear verbatim in what the
    tool prints for the matching fixture. Edit a tool, re-run, fix the README."""

    def assertLinesIn(self, lines, output):
        out = {l.rstrip() for l in output.splitlines()}
        missing = [l for l in lines if l.rstrip() not in out]
        self.assertEqual(missing, [], "README line not in real output")

    def readme_lines(self, *starts):
        text = prose_raw("README.md")
        return [l for l in text.splitlines() if l.strip().startswith(starts)]

    def test_hook_ranking(self):
        from _support import fixture, run_tool
        lines = self.readme_lines("->  85.6", "81.4 STRONG", "54.4 OK", "9.6 WEAK", "weakest:")
        self.assertEqual(len(lines), 8)
        self.assertLinesIn(lines, run_tool("hookscore", fixture("hooks.txt")).stdout)

    def test_beat_sheet(self):
        from _support import fixture, run_tool
        lines = self.readme_lines("BEAT SHEET", "0:00.0", "0:17.4", "0:20.4", "0:23.3")
        self.assertEqual(len(lines), 5)
        self.assertLinesIn(lines, run_tool("beats", fixture("script.txt"), "--target", "30").stdout)

    def test_caption(self):
        from _support import fixture, run_tool
        text = prose_raw("README.md")
        block = text[text.index("  WHAT THE FEED SHOWS"):]
        block = block[:block.index("```")]
        lines = [l for l in block.splitlines()
                 if l.strip().startswith(("PASS  ", "WARN  ", "| "))
                 ]
        self.assertEqual(len(lines), 12)
        out = run_tool("caption", fixture("caption.txt"), "--keywords",
                       "client contracts,freelance pricing").stdout
        self.assertLinesIn(lines, out)

    def test_swipe(self):
        from _support import fixture, run_tool
        lines = self.readme_lines("SWIPE FILE", "60.0x", "37.5x", "3.5x", "1.3x")
        self.assertEqual(len(lines), 5)
        self.assertLinesIn(lines, run_tool("swipe", fixture("captured.tsv")).stdout)

    def test_detect_panel(self):
        """The README panel is a two-column summary of the real one: the bar
        and score are verbatim, and every number in the summary must appear
        in that check's detail line."""
        from _support import fixture, run_tool
        names = ("BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE")
        rows = self.readme_lines(*names)
        self.assertEqual(len(rows), 5)
        out = run_tool("detect", fixture("bad_draft.txt")).stdout.splitlines()
        for row in rows:
            with self.subTest(row=row.strip()[:14]):
                m = re.match(r"(\s*[A-Z ]+?\s+[#.]+\s+[\d.]+)\s+(.*)$", row)
                self.assertIsNotNone(m, row)
                head, summary = m.groups()
                idx = [i for i, l in enumerate(out) if l.rstrip() == head.rstrip()]
                self.assertEqual(len(idx), 1, f"bar/score not in output: {head!r}")
                detail = out[idx[0] + 1]
                for num in re.findall(r"\d+(?:\.\d+)?", summary):
                    self.assertRegex(detail, r"(?<![\d.])" + re.escape(num) + r"(?![\d.])")

    def test_humanizer_delta(self):
        import tempfile
        from _support import fixture, run_tool
        with tempfile.TemporaryDirectory() as d:
            after = os.path.join(d, "after.txt")
            proc = run_tool("humanize", fixture("bad_draft.txt"), "-o", after)
            self.assertEqual(proc.returncode, 0)
            out = run_tool("detect", fixture("bad_draft.txt"), after).stdout
        self.assertLinesIn(self.readme_lines("29.3 FLAGGED  ->"), out)
        self.assertLinesIn(self.readme_lines("HUMAN SCORE   #######......"), out)


def prose_raw(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()
