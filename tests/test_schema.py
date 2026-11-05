"""Every object a tool prints with --json carries "schema": 1.

A program that calls the tools reads the JSON, and the schema number is how it
knows the shape it is reading. The class is "every place a tool prints JSON",
read from the source: the tools are the scripts with a --json flag, and a
script whose json.dumps argument is a conditional (one object or a list of
them) must be run here in both shapes. In a list, every element carries it.
"""

import ast
import glob
import json
import os
import unittest

from _support import SKILLS, TOOLS, fixture, run_tool

SCHEMA = 1

# How to run each tool with --json: (label, argv). en and pt-BR both.
RUNS = {
    "hookscore": [("one hook", ["--hook", "You lose $400 a month on this"]),
                  ("one hook pt-BR", ["--hook", "Você perde R$400 por mês nisso",
                                      "--lang", "pt-BR"]),
                  ("a list", [fixture("hooks.txt")]),
                  ("a list pt-BR", [fixture("hooks.pt-BR.txt"), "--lang", "pt-BR"])],
    "beats": [("script", [fixture("script.txt"), "--target", "30"]),
              ("script pt-BR", [fixture("script.pt-BR.txt"), "--lang", "pt-BR"])],
    "caption": [("caption", [fixture("caption.txt")]),
                ("caption pt-BR", [fixture("caption.pt-BR.txt"), "--lang", "pt-BR"])],
    "humanize": [("draft", [fixture("bad_draft.txt")]),
                 ("draft pt-BR", [fixture("good_draft.pt-BR.txt"), "--lang", "pt-BR"])],
    "detect": [("one draft", [fixture("good_draft.txt")]),
               ("one draft pt-BR", [fixture("good_draft.pt-BR.txt"), "--lang", "pt-BR"]),
               ("before/after", [fixture("bad_draft.txt"), fixture("good_draft.txt")])],
    "swipe": [("swipe", [fixture("captured.tsv")]),
              ("swipe pt-BR", [fixture("captured.pt-BR.tsv"), "--lang", "pt-BR"])],
}


def script_paths():
    return sorted(p for p in glob.glob(os.path.join(SKILLS, "*", "*.py"))
                  if not os.path.basename(p).startswith("_"))


def parse(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read())


def json_tools():
    """{name: path} of every script that has a --json flag, from the source."""
    out = {}
    for path in script_paths():
        for node in ast.walk(parse(path)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument"
                    and any(isinstance(a, ast.Constant) and a.value == "--json"
                            for a in node.args)):
                out[os.path.splitext(os.path.basename(path))[0]] = path
    return out


def dumps_calls(path):
    return [n for n in ast.walk(parse(path))
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "json.dumps"]


def schema_constant(path):
    for node in parse(path).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SCHEMA"):
            return ast.literal_eval(node.value)
    return None


def objects(data):
    return data if isinstance(data, list) else [data]


class EveryJsonToolIsRun(unittest.TestCase):
    def test_the_runs_cover_every_tool(self):
        tools = json_tools()
        self.assertEqual(set(tools), set(RUNS), "a --json tool with no run here, or a dead one")
        self.assertEqual(set(tools), set(TOOLS))

    def test_a_tool_with_two_shapes_is_run_in_both(self):
        for name, path in json_tools().items():
            two = any(isinstance(c.args[0], ast.IfExp) for c in dumps_calls(path))
            if not two:
                continue
            with self.subTest(tool=name):
                shapes = set()
                for _, argv in RUNS[name]:
                    proc = run_tool(name, *argv, "--json")
                    shapes.add(type(json.loads(proc.stdout)).__name__)
                self.assertEqual(shapes, {"dict", "list"})

    def test_one_json_call_per_tool(self):
        # A second json.dumps would be a second shape nobody runs here.
        for name, path in json_tools().items():
            with self.subTest(tool=name):
                self.assertEqual(len(dumps_calls(path)), 1)


class EveryObjectCarriesTheSchema(unittest.TestCase):
    def test_schema_in_every_object(self):
        for name, runs in RUNS.items():
            for label, argv in runs:
                with self.subTest(tool=name, run=label):
                    proc = run_tool(name, *argv, "--json")
                    self.assertNotIn("Traceback", proc.stderr)
                    for obj in objects(json.loads(proc.stdout)):
                        self.assertEqual(obj.get("schema"), SCHEMA)

    def test_schema_constant_is_the_same_everywhere(self):
        for name, path in json_tools().items():
            with self.subTest(tool=name):
                self.assertEqual(schema_constant(path), SCHEMA)


if __name__ == "__main__":
    unittest.main()
