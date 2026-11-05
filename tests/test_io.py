"""Class nets for the way every tool reads its input and writes its output.

1. Decomposed text (NFD). macOS pastes "você" as "voce" + U+0302. A combining
   mark is not `\\w` in `re`, so "atenção" in NFD reads as three words and
   "#ação" as "#a". The member is not one regex but every tool, so the net
   runs every tool from the command line on the same text in NFC and in NFD
   and asks for the same answer. Comparing the CLI, not one function, covers
   every path from the file to the printout (main, render, --json, -o/--out).

2. Files left open (ResourceWarning). Read from src: every `open(...)` in a
   script must be the head of a `with`. The CLI run also fails if Python,
   in dev mode, reports an unclosed file on any path the net exercises.

Both enumerate the tools from the tree (`script_paths`) and fail on a script
the case table does not cover.
"""

import ast
import glob
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest

from _support import ROOT, TOOLS
from test_invariants import data_strings, script_paths

# Accented words in every position the tools look at: pronoun, number and
# money, proper names, hashtags, a curly-quoted ask, a word split by NFD.
TEXT = (
    "Você perdeu R$ 3.000 em São Paulo porque ninguém explicou a atenção ao preço.\n"
    "A ação de Ângela começou às 9h com 12 clientes e terminou em três semanas.\n"
    "Salva esse post e comenta “ação” que eu te mando o guia. #ação #café\n"
)
TSV = ("account\tfollowers\tviews\thook\n"
       + "".join(f"@conta{i}\t1000\t{(i + 1) * 9000}\t{line}\n"
                 for i, line in enumerate(TEXT.splitlines())))

# Every tool, every way it writes: (input file contents, argument lists).
# "{in}" is the input file, "{out}" a file the tool may write.
CASES = {
    "hookscore": (TEXT, [["{in}"], ["{in}", "--json"], ["--hook", TEXT.splitlines()[0]]]),
    "beats": (TEXT, [["{in}", "--target", "30"], ["{in}", "--json"]]),
    "caption": (TEXT, [["{in}"], ["{in}", "--json", "--keywords", "ação,São Paulo"]]),
    "humanize": (TEXT, [["{in}", "--report"], ["{in}", "--json"], ["{in}", "-o", "{out}"]]),
    "detect": (TEXT, [["{in}"], ["{in}", "--json"], ["{in}", "{in}"]]),
    "swipe": (TSV, [["{in}"], ["{in}", "--json"], ["{in}", "--out", "{out}"]]),
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def nfd(s):
    return unicodedata.normalize("NFD", s)


def run_case(tool, contents, args, workdir):
    """Run a tool in `workdir` with relative paths, so two runs in two
    directories print the same thing. Returns (code, stdout, stderr, written)."""
    with open(os.path.join(workdir, "in.txt"), "w", encoding="utf-8") as fh:
        fh.write(contents)
    argv = [a.replace("{in}", "in.txt").replace("{out}", "out.txt") for a in args]
    proc = subprocess.run(
        [sys.executable, "-X", "dev", "-W", "always::ResourceWarning", TOOLS[tool], *argv],
        capture_output=True, text=True, encoding="utf-8", cwd=workdir, timeout=60)
    out = os.path.join(workdir, "out.txt")
    written = None
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            written = fh.read()
        os.remove(out)
    return proc.returncode, proc.stdout, proc.stderr, written


class CaseTableCoversTheTree(unittest.TestCase):
    def test_every_script_has_a_case(self):
        by_path = {os.path.realpath(p): n for n, p in TOOLS.items()}
        missing = [os.path.relpath(p, ROOT) for p in script_paths()
                   if by_path.get(os.path.realpath(p)) not in CASES]
        self.assertEqual(missing, [], "add these to CASES in tests/test_io.py")

    def test_witness_is_split_by_nfd(self):
        # The net is only a net if the decomposed copy really differs.
        self.assertNotEqual(nfd(TEXT), TEXT)
        self.assertEqual(nfc(TEXT), TEXT)


class DecomposedText(unittest.TestCase):
    def test_nfd_answers_like_nfc(self):
        bad = []
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for tool, (contents, arglists) in CASES.items():
                for args in arglists:
                    nfd_args = [nfd(x) for x in args]
                    want = run_case(tool, contents, args, a)
                    got = run_case(tool, nfd(contents), nfd_args, b)
                    got = tuple(nfc(x) if isinstance(x, str) else x for x in got)
                    if got != want:
                        bad.append((tool, args[:2]))
        self.assertEqual(bad, [])


class FilesAreClosed(unittest.TestCase):
    def test_every_open_is_a_with(self):
        bare = []
        # igtools/ is Python that ships too: the same rule.
        for path in script_paths() + sorted(glob.glob(os.path.join(ROOT, "igtools", "*.py"))):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            heads = {id(item.context_expr) for node in ast.walk(tree)
                     if isinstance(node, ast.With) for item in node.items}
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "open" and id(node) not in heads):
                    bare.append(f"{os.path.relpath(path, ROOT)}:{node.lineno}")
        self.assertEqual(bare, [], "open() outside a with leaks the file handle")

    def test_no_resource_warning_on_any_path(self):
        leaks = []
        with tempfile.TemporaryDirectory() as d:
            for tool, (contents, arglists) in CASES.items():
                for args in arglists:
                    _, _, err, _ = run_case(tool, contents, args, d)
                    if "ResourceWarning" in err:
                        leaks.append((tool, args[:2]))
        self.assertEqual(leaks, [])


class CopiesAndData(unittest.TestCase):
    def test_read_text_is_the_same_everywhere(self):
        # Copied so each folder stands alone, like the regexes: copies must not drift.
        copies = {}
        for path in script_paths():
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == "read_text":
                    copies[os.path.relpath(path, ROOT)] = ast.dump(node)
        self.assertEqual(len(copies), len(script_paths()), "a script without read_text")
        self.assertEqual(len(set(copies.values())), 1, sorted(copies))

    def test_data_is_composed(self):
        # The tools compose their input, so a decomposed JSON string never matches.
        found = list(data_strings())
        self.assertGreater(len(found), 100)  # the scan reached the data
        bad = [(f, k, v[:40]) for f, k, v in found if v != nfc(v)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
