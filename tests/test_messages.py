"""Every sentence a tool prints comes from its language file (fase 2, passo 3b).

The class is "every human phrase in the code", which no grep can list. So the
net reads the source: every string literal with a letter in it, in all six
scripts, is a phrase unless it sits where a phrase cannot be (docstring, regex,
argparse, subscript) or is a contract token. Contract tokens are not written
by hand: they are the key names of the data files plus what the tools actually
emit as `--json` keys, check ids and verdicts. What is left must be zero.

Then the messages themselves: every key the code asks for exists, no key is
dead, the template's fields are the call's keywords, and a pt-BR file whose
every message is wrapped in a marker shows the marker under `--lang pt-BR`
and nothing else changes.
"""

import ast
import glob
import json
import os
import re
import shutil
import string
import tempfile
import unittest

from _support import SKILLS, TOOLS, fixture, read_fixture, run_tool

# Where each tool's messages live: (file relative to its folder, section).
MESSAGES = {
    "hookscore": ("lang/{}.json", "hookscore"),
    "beats": ("lang/{}.json", "beats"),
    "caption": ("lang/{}.json", "caption"),
    "humanize": ("lang/{}.json", "humanize"),
    "detect": ("lang/{}.json", "detect"),
    "swipe": ("lang/{}.json", "swipe"),
}

# The one way a phrase reaches the output. Copied in every script.
SAY = "say"

# Literals that are phrases but stay in the code, each with its reason.
# Matched as a substring of the literal (an f-string counts as one literal,
# its values shown as {}). Checked: an exemption nothing matches is stale.
EXEMPT_TEXT = {
    "cannot load": "the language file itself failed to load; there is no language to say it in",
}
# Whole functions left out, each with its reason. Checked: must exist.
EXEMPT_FUNCS = {
    "pick_lang": "the --lang auto diagnostic is about the choice itself, before a language is loaded",
    "pick_swipe_lang": "same diagnostic, swipe's copy",
    "read_text": "the input fails to read before any language is chosen (--lang auto needs the text)",
    "match_for": "hooks.json schema validation; the reason sits inside the translated "
                 "cannot_load_hooks sentence, like json's own parse errors",
    "check_lexicon": "slop.<lang>.json schema validation (humanize and detect); its reason "
                     "follows \"cannot load the lexicon\" (exempt above, same reason), like "
                     "json's own parse errors",
}
# Code tokens that are neither phrases nor emitted contract, each with its reason.
CODE_TOKENS = {
    "utf-8": "file encoding",
    "stdin": "the name standard input goes by in an error, as read_text shows it",
    "NFC": "unicodedata form",
    "__main__": "module guard",
    ".json": "file name part",
    "slop.": "file name part",
    "hooks.json": "file name",
    "ig-reel": "sibling folder name",
    "uniform-bullets": "structural tell id, same family as the `id` fields in slop.en.json",
    "hanging": "structural tell id, same",
    "role": "key of a held lexicon word, inside humanize: no replacement fits that use",
    "Cf": "unicodedata category",
    "en": "language code",
    "pt-BR": "language code",
}
# Contract tokens the witness runs do not happen to emit, each with its reason.
CONTRACT_EXTRA = {
    "READY": "caption verdict; no witness caption is clean",
    "follower count": "swipe baseline enum when the batch has no account median",
}
# --json fields whose values are an enum (contract), not a sentence.
ENUM_FIELDS = {"check", "status", "verdict", "label", "baseline", "lang", "action"}
# A literal that is only a file name ("slop.{}.json").
FILE_NAME = re.compile(r"^[\w.{}-]*\.json$")

# Calls whose arguments are not output a language decides: argparse builds
# --help before --lang is parsed.
ARGPARSE = {"ArgumentParser", "add_argument", "add_mutually_exclusive_group"}
RE_CALLS = {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub", "split"}
LETTER = re.compile(r"[^\W\d_]{2,}")

HOOKS = "\n".join([
    "Nobody tells you that your first 30 reels are supposed to flop.",
    "I lost $18,000 because of one missing contract.",
    "Stop scrolling if you want to grow on Instagram in 2026 🔥",
    "Hey guys, today I wanted to talk about content strategy #growth",
    "So basically I want to show you my workflow",
    "Save this clause before the next client signs",
]) + "\n"
CAPTIONS = [
    read_fixture("caption.txt"),
    "\nopens blank",
    "@someone look at this #a #b #c #d #e #f #g\nComment GUIDE below and follow for more",
    "Short one with a link loja.com/x and https://x.com/y 🔥🔥🔥🔥 ✨✨ 💯",
    "No ask here at all, just words about 3 contracts that cost me $4,000 in March "
    "and the clause I now put first. #freelance #explore",
]

# Invocations that walk the branches. (args, stdin); "{tmp}" is a scratch dir.
RUNS = {
    "hookscore": [([fixture("hooks.txt")], None), (["-"], HOOKS),
                  (["--hook", "I lost $18,000 because of one missing contract."], None),
                  (["--hook", "Hey guys #growth 🔥"], None)],
    "beats": [([fixture("script.txt"), "--target", t], None) for t in ("10", "30", "90")]
             + [(["-", "--target", "30"], "Hello there.\nOk.\n")],
    "caption": [(["-", "--keywords", "contracts,freelance,pricing"], c) for c in CAPTIONS],
    "humanize": [([fixture("bad_draft.txt"), "--report"], None),
                 ([fixture("good_draft.txt"), "--report"], None),
                 (["-", "--report"], "​If you love design, delve into it. A. B. C.\n")],
    "detect": [([fixture("good_draft.txt"), fixture("bad_draft.txt")], None),
               ([fixture("bad_draft.txt")], None), (["-"], "Too short.\n")],
    "swipe": [([fixture("captured.tsv")], None),
              ([fixture("captured.tsv"), "--out", "{tmp}/swipe.md"], None)],
}


def folder_of(tool):
    return os.path.dirname(TOOLS[tool])


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def messages_of(tool, root=None):
    rel, section = MESSAGES[tool]
    base = os.path.join(root, os.path.basename(folder_of(tool))) if root else folder_of(tool)
    return read_json(os.path.join(base, rel.format("en")))[section]["messages"]


def _walk_keys(x, keys, values):
    if isinstance(x, dict):
        for k, v in x.items():
            keys.add(k)
            if k in ENUM_FIELDS and isinstance(v, str):
                values.add(v)
            if k == "checks" and isinstance(v, dict):
                keys.update(v)
            _walk_keys(v, keys, values)
    elif isinstance(x, list):
        for v in x:
            _walk_keys(v, keys, values)


def _contract():
    """Data-file key names + every key, check id and verdict the tools emit."""
    keys, values = set(), set()
    for path in glob.glob(os.path.join(SKILLS, "*", "*.json")) + \
            glob.glob(os.path.join(SKILLS, "*", "lang", "en.json")):
        _walk_keys(read_json(path), keys, values)
    with tempfile.TemporaryDirectory() as tmp:
        for tool, runs in RUNS.items():
            for args, stdin in runs:
                args = [a.replace("{tmp}", tmp) for a in args]
                if "--report" in args:
                    continue
                proc = run_tool(tool, *args, "--json", stdin=stdin)
                try:
                    _walk_keys(json.loads(proc.stdout), keys, values)
                except ValueError:
                    pass
    return keys | values | set(CONTRACT_EXTRA)


CONTRACT = _contract()


def _skipped_nodes(tree):
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body \
                and isinstance(node.body[0], ast.Expr) \
                and isinstance(node.body[0].value, ast.Constant):
            skip.add(id(node.body[0].value))
        sub = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ARGPARSE or (
                    node.func.attr in RE_CALLS and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re"):
                sub = node
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == SAY and len(node.args) > 1:
            sub = node.args[1]            # the key, checked by MessageKeys
        elif isinstance(node, ast.Subscript):
            sub = node.slice
        elif isinstance(node, ast.Dict):
            # keys are names the code reads back; values are still scanned
            skip.update(id(k) for k in node.keys if k is not None)
        elif isinstance(node, ast.Compare):
            # a literal compared against is internal state, not output
            skip.update(id(c) for c in [node.left, *node.comparators]
                        if isinstance(c, ast.Constant))
        elif isinstance(node, ast.FunctionDef) and node.name in EXEMPT_FUNCS:
            sub = node
        if sub is not None:
            skip.update(id(n) for n in ast.walk(sub))
    return skip


def human_literals(path):
    """(line, text) for every phrase literal left in a script."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    skip = _skipped_nodes(tree)
    inner = set()
    found = []
    for node in ast.walk(tree):
        if id(node) in skip or id(node) in inner:
            continue
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                inner.update(id(n) for n in ast.walk(v))
                parts.append(v.value if isinstance(v, ast.Constant) else "{}")
            text = "".join(parts)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        bare = text.strip()
        if "\x00" in text or not LETTER.search(text.replace("{}", "")):
            continue
        if bare in CONTRACT or bare in CODE_TOKENS or FILE_NAME.match(bare):
            continue
        if any(s in text for s in EXEMPT_TEXT):
            continue
        found.append((node.lineno, text))
    return found


def say_calls(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == SAY]


class NoPhraseInCode(unittest.TestCase):
    def test_scanner_sees_a_planted_phrase(self):
        src = ('import re, argparse\n'
               'def f(n):\n    """Docstring is fine."""\n'
               '    re.compile(r"never seen")\n'
               '    argparse.ArgumentParser(description="help is fine")\n'
               '    print("utf-8", "verdict")\n'
               '    print(f"{n} words left over")\n'
               '    return "too short to judge"\n')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "planted.py")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src)
            texts = sorted(t for _, t in human_literals(p))
        self.assertEqual(texts, ["too short to judge", "{} words left over"])

    def test_scripts_carry_no_phrase(self):
        for tool, path in TOOLS.items():
            with self.subTest(tool=tool):
                found = human_literals(path)
                self.assertEqual(found, [], f"{tool}: {len(found)} phrase(s) belong in "
                                 f"{MESSAGES[tool][0].format('en')} -> messages:\n" +
                                 "\n".join(f"  {path}:{ln}: {t!r}" for ln, t in found))

    def test_every_tool_is_in_the_net(self):
        self.assertEqual(set(MESSAGES), set(TOOLS))

    def test_exemptions_are_alive(self):
        srcs = {}
        for tool, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                srcs[tool] = fh.read()
        everything = "\n".join(srcs.values())
        for s in EXEMPT_TEXT:
            with self.subTest(text=s):
                self.assertIn(s, everything, f"stale EXEMPT_TEXT {s!r}")
        for f in EXEMPT_FUNCS:
            with self.subTest(func=f):
                self.assertRegex(everything, rf"\ndef {f}\(", f"stale EXEMPT_FUNCS {f}")
        for t in CODE_TOKENS:
            with self.subTest(token=t):
                self.assertTrue(re.search(r"[\"']" + re.escape(t) + r"[\"']", everything),
                                f"stale CODE_TOKENS {t!r}")
        for t in CONTRACT_EXTRA:
            with self.subTest(contract=t):
                self.assertIn(t, everything, f"stale CONTRACT_EXTRA {t!r}")


class MessageKeys(unittest.TestCase):
    def test_keys_exist_none_dead_fields_match(self):
        for tool, path in TOOLS.items():
            with self.subTest(tool=tool):
                msgs = messages_of(tool)
                used = set()
                for call in say_calls(path):
                    where = f"{tool}:{call.lineno}"
                    key = call.args[1] if len(call.args) > 1 else None
                    self.assertTrue(isinstance(key, ast.Constant) and isinstance(key.value, str),
                                    f"{where}: say() key must be a string literal")
                    self.assertEqual(len(call.args), 2, f"{where}: values go as keywords")
                    self.assertFalse(any(k.arg is None for k in call.keywords),
                                     f"{where}: no **kwargs, the net reads the names")
                    used.add(key.value)
                    self.assertIn(key.value, msgs, f"{where}: no message {key.value!r}")
                    fields = {f.split(".")[0].split("[")[0]
                              for _, f, _, _ in string.Formatter().parse(msgs[key.value])
                              if f is not None}
                    self.assertEqual(fields, {k.arg for k in call.keywords},
                                     f"{where}: fields of {key.value!r} != keywords")
                self.assertEqual(set(msgs) - used, set(), f"{tool}: dead message keys")

    def test_every_language_has_every_message(self):
        # A translated file missing a key would crash in say(); same keys, same fields.
        for tool, (rel, section) in MESSAGES.items():
            en = messages_of(tool)
            pattern = os.path.join(folder_of(tool), rel.format("*"))
            for path in glob.glob(pattern):
                other = read_json(path)[section]["messages"]
                with self.subTest(tool=tool, file=os.path.basename(path)):
                    self.assertEqual(set(other), set(en), f"{path}: message keys differ from en")
                    for k, v in en.items():
                        f = lambda t: sorted(x[1] for x in string.Formatter().parse(t) if x[1])
                        self.assertEqual(f(other[k]), f(v), f"{path}: fields of {k!r}")

    def test_one_say_everywhere(self):
        dumps = {}
        for tool, path in TOOLS.items():
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == SAY]
            with self.subTest(tool=tool):
                self.assertEqual(len(fns), 1, f"{tool} has no say()")
                dumps[tool] = ast.dump(fns[0])
        self.assertEqual(len(set(dumps.values())), 1, "say() copies drifted")


MARK = re.compile(r"[⟦⟧]")
EN_MARK, PT_MARK = ("⟦", "⟧"), ("⟪", "⟫")


def _marked(path, marks):
    data = read_json(path)
    for section in data.values():
        if isinstance(section, dict) and isinstance(section.get("messages"), dict):
            m = section["messages"]
            for k, v in m.items():
                m[k] = marks[0] + v + marks[1]
    return data


def _pt_like_en(obj):
    """Give every per-language value ({"en": ..., "pt-BR": ...}) its en value
    under pt-BR, in place. True if anything changed."""
    changed = False
    if isinstance(obj, dict):
        if "en" in obj and set(obj) <= {"en", "pt-BR"} and obj.get("pt-BR") != obj["en"]:
            obj["pt-BR"] = obj["en"]
            changed = True
        for v in obj.values():
            changed |= _pt_like_en(v)
    elif isinstance(obj, list):
        for v in obj:
            changed |= _pt_like_en(v)
    return changed


def plant(d, tool):
    """Lone copy (swipe takes ig-reel along) with pt-BR = en for every
    language file, every pt-BR message wrapped in ⟪ ⟫. Returns the script
    and mark_en(), which then wraps every en message in ⟦ ⟧."""
    folders = {os.path.basename(folder_of(tool))}
    if tool == "swipe":
        folders.add("ig-reel")
    ens = []
    for f in folders:
        shutil.copytree(os.path.join(SKILLS, f), os.path.join(d, f),
                        ignore=shutil.ignore_patterns("__pycache__"))
        for en in glob.glob(os.path.join(d, f, "*.en.json")) + \
                glob.glob(os.path.join(d, f, "lang", "en.json")):
            ens.append(en)
            write_json(en.replace("en.json", "pt-BR.json"), _marked(en, PT_MARK))
        for path in glob.glob(os.path.join(d, f, "*.json")):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if _pt_like_en(data):          # hooks.json `match`: pt-BR = en there too
                write_json(path, data)

    def mark_en():
        for en in ens:
            write_json(en, _marked(en, EN_MARK))
    return (os.path.join(d, os.path.basename(folder_of(tool)), os.path.basename(TOOLS[tool])),
            mark_en)


def squash(s):
    # A marker inside a padded column moves the padding, and a rule drawn to
    # the header's length grows with it; the words must not move.
    return re.sub(r"[=-]{3,}", "---", re.sub(r" +", " ", MARK.sub("", s)))


def written(d):
    """Files a run wrote with --out / -o (the top of the scratch dir): read and removed."""
    out = {}
    for name in sorted(os.listdir(d)):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out[name] = fh.read()
            os.remove(path)
    return "".join(f"--- {k}\n{v}" for k, v in out.items())


def as_en(s):
    return s.replace(PT_MARK[0], EN_MARK[0]).replace(PT_MARK[1], EN_MARK[1])


class MessagesFollowTheFlag(unittest.TestCase):
    """en marked ⟦ ⟧ and pt-BR marked ⟪ ⟫ side by side: under --lang pt-BR a
    ⟦ is an en sentence that leaked (a call that forgot its lang), and with
    the marks swapped the output must be the en one exactly."""

    def test_pt_br_says_the_planted_messages(self):
        for tool, runs in RUNS.items():
            said = 0          # a run may print no sentence (clean --json); the tool must
            for args, stdin in runs:
                for extra in ((), ("--json",)):
                    with self.subTest(tool=tool, args=args, json=bool(extra)), \
                            tempfile.TemporaryDirectory() as d:
                        a = [x.replace("{tmp}", d) for x in args]
                        before = run_tool(tool, *a, *extra, stdin=stdin)
                        before.stdout += written(d)
                        script, mark_en = plant(d, tool)
                        en = run_tool(script, *a, *extra, "--lang", "en", stdin=stdin)
                        en.stdout += written(d)
                        self.assertEqual((en.returncode, en.stdout, en.stderr),
                                         (before.returncode, before.stdout,
                                          before.stderr.replace(SKILLS, d)),
                                         "en moved with pt-BR beside it")
                        mark_en()
                        en = run_tool(script, *a, *extra, "--lang", "en", stdin=stdin)
                        en.stdout += written(d)
                        pt = run_tool(script, *a, *extra, "--lang", "pt-BR", stdin=stdin)
                        pt.stdout += written(d)
                        self.assertNotIn("Traceback", pt.stderr)
                        self.assertEqual(pt.returncode, en.returncode, pt.stderr)
                        self.assertNotIn(EN_MARK[0], pt.stdout + pt.stderr,
                                         "an en sentence leaked into --lang pt-BR")
                        self.assertNotIn(PT_MARK[0], en.stdout + en.stderr)
                        self.assertEqual(as_en(pt.stdout), en.stdout)
                        self.assertEqual(as_en(pt.stderr), en.stderr)
                        self.assertEqual(squash(en.stdout), squash(before.stdout),
                                         "en words moved: a sentence is not in its file")
                        said += PT_MARK[0] in pt.stdout + pt.stderr
            with self.subTest(tool=tool):
                self.assertGreater(said, len(runs), f"{tool}: few messages came from pt-BR")


if __name__ == "__main__":
    unittest.main()
