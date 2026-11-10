"""--lang reaches every function that reads language data (fase 2, passo 3).

The class is "every read of language data", which no grep can list: the data
used to be loaded at import into module constants and read deep inside the
checks. So the net is derived from the data files. For every key a tool reads,
a lone copy of the tool gets a planted pt-BR file equal to en with that one
key blanked; `--lang pt-BR` must give exactly what an en file with the key
blanked gives, and that reference must differ from plain en on the witness
input, or the case proves nothing. A key the tool does not read is declared
below, and the declaration is checked: blanking it must change nothing.
"""

import ast
import json
import os
import shutil
import tempfile
import unittest

from _support import SKILLS, TOOLS, fixture, load, read_fixture, run_tool

# Where each tool's language lives, relative to its folder, and the part of
# the file it reads (None = the whole file).
SOURCE = {
    "hookscore": ("lang/{}.json", "hookscore"),
    "beats": ("lang/{}.json", "beats"),
    "caption": ("lang/{}.json", "caption"),
    "humanize": ("slop.{}.json", None),
    "detect": ("slop.{}.json", None),
}

# Keys that describe the file, not the language's words.
METADATA = {"lang", "note", "version"}
# Read only by --lang auto; AutoPicks covers it.
AUTO_KEY = "auto"
# The sentences each tool prints: covered by tests/test_messages.py, which
# also plants a marked pt-BR file. Not a language key the witness can move.
MESSAGES_KEY = "messages"

# Tools whose messages sit in their own folder's lang/ (the language file the
# net plants is slop.<code>.json, or ig-reel's). A planted pt-BR needs the
# messages beside it; a copy of en says the same sentences.
MESSAGES_FOLDERS = ("ig-human", "ig-viral")

# Keys a tool does not read, with the reason. Checked: blanking one must leave
# the output as it was.
NOT_READ = {
    "detect": {
        "invisible": "humanize strips invisible characters; detect scores words",
        "typographic": "the typographic pass is humanize's",
        "connectives": "the splice tell is flagged by humanize's scan only",
        "conjunctions": "orphan conjunctions come from a deletion, and detect deletes nothing",
        "complementizers": "same: the 'that' left by a deleted opener",
        "inflection": "rules the test suite checks the lexicon with; the forms are entries",
        "article": "the article agrees after a replacement, and detect replaces nothing",
    },
    "humanize": {
        "note": "a note describes its section to the person editing it; no tool reads it",
        "voice": "voice is scored by detect; humanize does not rewrite pronouns",
        "inflection": "rules the test suite checks the lexicon with; the forms are entries",
    },
}

# Input on which every read key moves the output. One per tool, run with --json.
HOOKS = "\n".join([
    "Nobody tells you that your first 30 reels are supposed to flop.",
    "I lost $18,000 because of one missing contract.",
    "Stop scrolling if you want to grow on Instagram in 2026 🔥",
    "Hey guys, today I wanted to talk about content strategy",
    "Twenty grand gone on 3 weeks of bad ads, and I paid for it",
    "So basically I want to show you my workflow",
    "Save this clause before the next client signs",
    "You are losing money on every invoice you send late",
]) + "\n"
WITNESS = {
    "hookscore": (["-"], HOOKS),
    "beats": (["-", "--target", "30"], read_fixture("script.txt")),
    "caption": (["-"], read_fixture("caption.txt") + " #explore\n"),
    # bad_draft has no invisible character, splice or "that" after an opener,
    # and no deletion a dependent holds ("if" keeps "follow for more" here).
    "humanize": (["-"], read_fixture("bad_draft.txt")
                 + "\n\u200bHere's the thing that we hit 10k. It is crucial \u2014 also, it's proof.\n"
                 + "It was a captivating reel.\nFollow for more if you love design.\n"),
    "detect": ([fixture("good_draft.txt"), "-"],
               read_fixture("bad_draft.txt") + "\nFollow for more if you love design.\n"),
}


def blank(value):
    """The emptiest value of the same shape: a list or a dict empties, a regex never matches."""
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    if isinstance(value, str):
        return "(?!)"
    raise TypeError(type(value))


def key_paths(tool):
    """Every language key of the tool's en file, as paths into the JSON.
    A dict of regexes (`voice`) counts each of its keys."""
    rel, section = SOURCE[tool]
    with open(os.path.join(os.path.dirname(TOOLS[tool]), rel.format("en")),
              encoding="utf-8") as fh:
        data = json.load(fh)
    base = data[section] if section else data
    prefix = (section,) if section else ()
    out = []
    for k, v in base.items():
        if k in METADATA or k in (AUTO_KEY, MESSAGES_KEY):
            continue
        if isinstance(v, dict):
            out += [prefix + (k, sub) for sub in v]
        else:
            out.append(prefix + (k,))
    return out


def blank_at(data, path):
    node = data
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = blank(node[path[-1]])


def folder_of(tool):
    return os.path.basename(os.path.dirname(TOOLS[tool]))


def lone(d, *folders):
    """A lone copy with en only: the net plants the other language files it
    tests, so a shipped pt-BR never stands in for one (or for its absence).
    The shipped pt-BR files are checked in tests/test_pt_br.py."""
    for f in folders:
        shutil.copytree(os.path.join(SKILLS, f), os.path.join(d, f),
                        ignore=shutil.ignore_patterns("__pycache__", "*pt-BR.json"))


def plant_messages(d, folder):
    """pt-BR messages for the folders that keep them apart from the language
    data: the en file, copied. Folders where messages ride in the language
    file need nothing: the test plants that file whole."""
    if folder not in MESSAGES_FOLDERS:
        return
    lang = os.path.join(d, folder, "lang")
    shutil.copy(os.path.join(lang, "en.json"), os.path.join(lang, "pt-BR.json"))


def data_path(d, tool, code):
    rel, _ = SOURCE[tool]
    return os.path.join(d, folder_of(tool), rel.format(code))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def run_in(d, tool, *extra):
    args, stdin = WITNESS[tool]
    script = os.path.join(d, folder_of(tool), os.path.basename(TOOLS[tool]))
    return run_tool(script, *args, "--json", *extra, stdin=stdin)


class EveryKeyFollowsTheFlag(unittest.TestCase):
    def outputs(self, tool, path):
        """(plain en, en with the key blanked, pt-BR planted with the key blanked)."""
        with tempfile.TemporaryDirectory() as d:
            lone(d, folder_of(tool))
            en = data_path(d, tool, "en")
            plain = run_in(d, tool, "--lang", "en")
            data = read_json(en)
            blank_at(data, path)
            write_json(data_path(d, tool, "pt-BR"), data)
            plant_messages(d, folder_of(tool))
            planted = run_in(d, tool, "--lang", "pt-BR")
            # The plain en run again, now that pt-BR sits beside it.
            again = run_in(d, tool, "--lang", "en")
            write_json(en, data)
            reference = run_in(d, tool, "--lang", "en")
        return plain, again, reference, planted

    def test_every_read_key(self):
        for tool in SOURCE:
            exempt = NOT_READ.get(tool, {})
            for path in key_paths(tool):
                name = ".".join(path)
                with self.subTest(tool=tool, key=name):
                    plain, again, reference, planted = self.outputs(tool, path)
                    self.assertNotIn("Traceback", planted.stderr + reference.stderr)
                    self.assertEqual(plain.stdout, again.stdout, "pt-BR leaked into en")
                    if path[-1] in exempt or (len(path) > 1 and path[-2] in exempt):
                        self.assertEqual(plain.stdout, reference.stdout,
                                         f"{tool} is declared not to read {name}, "
                                         "but blanking it moved the output")
                        continue
                    self.assertNotEqual(plain.stdout, reference.stdout,
                                        f"witness for {tool} does not exercise {name}")
                    self.assertEqual(planted.returncode, reference.returncode)
                    self.assertEqual(planted.stdout, reference.stdout,
                                     f"{tool} --lang pt-BR did not read {name} from pt-BR")

    def test_exemptions_name_real_keys(self):
        for tool, keys in NOT_READ.items():
            names = {p[-1] for p in key_paths(tool)} | {p[-2] for p in key_paths(tool)
                                                         if len(p) > 1}
            for k in keys:
                with self.subTest(tool=tool, key=k):
                    self.assertIn(k, names, f"stale exemption {tool}:{k}")

    def test_every_tool_with_language_is_in_the_net(self):
        # A tool that gains a data file must get a SOURCE entry.
        for tool, path in TOOLS.items():
            if tool == "swipe":
                continue                  # reads ig-reel's, covered by SwipeForwards
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if "load_lang" in src or "load_lexicon" in src:
                self.assertIn(tool, SOURCE, f"{tool} reads language data but is not in SOURCE")


class MissingLanguageFailsClosed(unittest.TestCase):
    def test_flag_without_file(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                lone(d, folder_of(tool))
                proc = run_in(d, tool, "--lang", "pt-BR")
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertIn(os.path.basename(data_path(d, tool, "pt-BR")), proc.stderr)

    def test_unknown_code_is_rejected(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                proc = run_tool(tool, "--lang", "xx", stdin="x\n")
                self.assertEqual(proc.returncode, 2)

    def test_default_is_en(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                lone(d, folder_of(tool))
                default = run_in(d, tool)
                explicit = run_in(d, tool, "--lang", "en")
                self.assertEqual(default.stdout, explicit.stdout)
                self.assertEqual(default.returncode, explicit.returncode)

    def test_lexicon_beats_lang(self):
        # --lexicon names a file; --lang only picks the default one.
        for tool in ("humanize", "detect"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                lone(d, folder_of(tool))
                en = data_path(d, tool, "en")
                plant_messages(d, folder_of(tool))
                plain = run_in(d, tool)
                both = run_in(d, tool, "--lang", "pt-BR", "--lexicon", en)
                self.assertEqual(both.returncode, plain.returncode, both.stderr)
                self.assertEqual(both.stdout, plain.stdout)


PT = "Você não sabe o que a gente perdeu com isso, mas é muito mais do que parece.\n"
EN = "You have no idea what we lost on this, and it is a lot more than it looks.\n"
PT_STOPWORDS = ["o", "a", "que", "de", "não", "é", "com", "mas", "você", "do", "isso", "mais"]


class AutoPicks(unittest.TestCase):
    """--lang auto counts stopwords over the languages that have a file."""

    def planted(self, d, tool):
        lone(d, folder_of(tool))
        data = read_json(data_path(d, tool, "en"))
        data["auto"] = {"stopwords": PT_STOPWORDS}
        write_json(data_path(d, tool, "pt-BR"), data)
        plant_messages(d, folder_of(tool))

    def run_text(self, d, tool, text, *flags):
        script = os.path.join(d, folder_of(tool), os.path.basename(TOOLS[tool]))
        args = ["--hook", text.strip()] if tool == "hookscore" else ["-"]
        return run_tool(script, *args, "--json", *flags,
                        stdin=None if tool == "hookscore" else text)

    def test_portuguese_picks_pt(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                self.planted(d, tool)
                auto = self.run_text(d, tool, PT, "--lang", "auto")
                pt = self.run_text(d, tool, PT, "--lang", "pt-BR")
                self.assertIn("lang: auto -> pt-BR", auto.stderr)
                self.assertEqual(auto.stdout, pt.stdout)
                self.assertEqual(auto.returncode, pt.returncode)

    def test_decomposed_portuguese_picks_pt(self):
        # Pasted from macOS, "você" arrives as "vo" + "c" + U+0302: compose first.
        import unicodedata
        nfd = unicodedata.normalize("NFD", PT)
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                self.planted(d, tool)
                data = read_json(data_path(d, tool, "pt-BR"))
                # Only the accented stopwords, so a split word cannot score.
                data["auto"] = {"stopwords": ["você", "não", "é"]}
                write_json(data_path(d, tool, "pt-BR"), data)
                plant_messages(d, folder_of(tool))
                auto = self.run_text(d, tool, nfd, "--lang", "auto")
                self.assertIn("lang: auto -> pt-BR", auto.stderr)

    def test_english_picks_en(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                self.planted(d, tool)
                auto = self.run_text(d, tool, EN, "--lang", "auto")
                self.assertIn("lang: auto -> en", auto.stderr)
                self.assertEqual(auto.stdout, self.run_text(d, tool, EN, "--lang", "en").stdout)

    def test_tie_falls_back_to_en_with_a_warning(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                self.planted(d, tool)
                auto = self.run_text(d, tool, "12345 67890\n", "--lang", "auto")
                self.assertIn("lang: auto -> en", auto.stderr)
                self.assertIn("tie", auto.stderr)

    def test_only_en_on_disk(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                lone(d, folder_of(tool))
                auto = self.run_text(d, tool, PT, "--lang", "auto")
                self.assertNotIn("Traceback", auto.stderr)
                self.assertIn("lang: auto -> en", auto.stderr)

    def test_stdout_is_untouched(self):
        # The choice goes to stderr only; --json stays parseable.
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                self.planted(d, tool)
                json.loads(self.run_text(d, tool, PT, "--lang", "auto").stdout)

    def test_en_files_carry_stopwords(self):
        for tool in SOURCE:
            with self.subTest(tool=tool):
                rel, _ = SOURCE[tool]
                data = read_json(os.path.join(os.path.dirname(TOOLS[tool]), rel.format("en")))
                self.assertGreaterEqual(len(data[AUTO_KEY]["stopwords"]), 10)

    def test_pick_lang_copies_are_equal(self):
        sources = {}
        for tool, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for node in ast.parse(src).body:
                if isinstance(node, ast.FunctionDef) and node.name == "pick_lang":
                    sources[tool] = ast.get_source_segment(src, node)
        self.assertEqual(set(sources), set(SOURCE), "pick_lang missing in a tool")
        first = next(iter(sources.values()))
        for tool, s in sources.items():
            with self.subTest(tool=tool):
                self.assertEqual(s, first)


class InProcess(unittest.TestCase):
    """The library path: two languages in one process do not bleed (a program that imports the tools)."""

    def module(self, d, tool):
        lone(d, folder_of(tool))
        data = read_json(data_path(d, tool, "en"))
        for path in key_paths(tool):
            blank_at(data, path)
        write_json(data_path(d, tool, "pt-BR"), data)
        plant_messages(d, folder_of(tool))
        import importlib.util
        path = os.path.join(d, folder_of(tool), os.path.basename(TOOLS[tool]))
        spec = importlib.util.spec_from_file_location(f"lf_{tool}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def call(self, mod, tool, lang):
        hook = "I lost $18,000 because of one missing contract."
        if tool == "hookscore":
            return mod.run(hook, lang=lang)
        if tool == "beats":
            return mod.analyse(read_fixture("script.txt"), target=30, lang=lang)
        if tool == "caption":
            return mod.analyse(read_fixture("caption.txt"), lang=lang)
        lex = mod.load_lexicon(lang=lang)
        if tool == "detect":
            return mod.run(read_fixture("bad_draft.txt"), lex)
        return mod.humanize(read_fixture("bad_draft.txt"), lex)

    def test_alternating_languages(self):
        for tool in SOURCE:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as d:
                mod = self.module(d, tool)
                en1 = repr(self.call(mod, tool, "en"))
                pt = repr(self.call(mod, tool, "pt-BR"))
                en2 = repr(self.call(mod, tool, "en"))
                self.assertEqual(en1, en2, "pt-BR leaked into en")
                self.assertNotEqual(en1, pt)

    def test_default_is_en(self):
        mod = load("hookscore")
        hook = "I lost $18,000 because of one missing contract."
        self.assertEqual(repr(mod.run(hook)), repr(mod.run(hook, lang="en")))


# Names bound at module level from language data. After passo 3 there are none:
# the data travels as an argument.
LANG_SOURCES = {"_LANG", "load_lang", "load_lexicon", "load_messages"}


class NoLanguageInModuleState(unittest.TestCase):
    def test_no_module_constant_from_language_data(self):
        for tool, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in tree.body:
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.Try):
                    targets = [t for n in node.body if isinstance(n, ast.Assign)
                               for t in n.targets]
                for t in targets:
                    value = node.value if isinstance(node, ast.Assign) else None
                    names = {n.id for n in ast.walk(value or node)
                             if isinstance(n, ast.Name)}
                    with self.subTest(tool=tool, line=t.lineno):
                        self.assertFalse(names & LANG_SOURCES,
                                         f"{tool}:{t.lineno} keeps language data in a "
                                         "module constant")


class SwipeForwards(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        lone(self.d, "ig-viral", "ig-reel")
        plant_messages(self.d, "ig-viral")
        self.script = os.path.join(self.d, "ig-viral", "swipe.py")

    def tearDown(self):
        shutil.rmtree(self.d)

    def run_swipe(self, *flags):
        proc = run_tool(self.script, fixture("captured.tsv"), "--json", *flags)
        return proc, json.loads(proc.stdout)

    def test_lang_reaches_hookscore(self):
        en = os.path.join(self.d, "ig-reel", "lang", "en.json")
        data = read_json(en)
        for path in key_paths("hookscore"):
            blank_at(data, path)
        write_json(os.path.join(self.d, "ig-reel", "lang", "pt-BR.json"), data)
        _, plain = self.run_swipe("--lang", "en")
        proc, pt = self.run_swipe("--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual([r["hook_score"] for r in plain["reels"]],
                            [r["hook_score"] for r in pt["reels"]])
        _, again = self.run_swipe("--lang", "en")
        self.assertEqual(plain, again)

    def test_missing_language_degrades(self):
        proc, out = self.run_swipe("--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("pt-BR.json", proc.stderr)
        self.assertTrue(all(r["hook_score"] is None for r in out["reels"]))

    def test_auto(self):
        proc, _ = self.run_swipe("--lang", "auto")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("lang: auto -> en", proc.stderr)


if __name__ == "__main__":
    unittest.main()
