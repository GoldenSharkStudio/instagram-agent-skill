"""Shared helpers for the test suite. stdlib only, like the tools."""

import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

TOOLS = {
    "hookscore": os.path.join(SKILLS, "ig-reel", "hookscore.py"),
    "beats": os.path.join(SKILLS, "ig-reel", "beats.py"),
    "caption": os.path.join(SKILLS, "ig-caption", "caption.py"),
    "humanize": os.path.join(SKILLS, "ig-human", "humanize.py"),
    "detect": os.path.join(SKILLS, "ig-human", "detect.py"),
    "swipe": os.path.join(SKILLS, "ig-viral", "swipe.py"),
}


def fixture(name):
    return os.path.join(FIXTURES, name)


def read_fixture(name):
    with open(fixture(name), encoding="utf-8") as fh:
        return fh.read()


def run_tool(script, *args, stdin=None, cwd=None):
    """Run a tool as the user would. `script` is a TOOLS key or a path."""
    path = TOOLS.get(script, script)
    return subprocess.run(
        [sys.executable, path, *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        cwd=cwd, timeout=60,
    )


def run_json(script, *args, stdin=None):
    proc = run_tool(script, *args, "--json", stdin=stdin)
    return proc, json.loads(proc.stdout)


_loaded = {}


def load(name):
    """Import a tool as a module, by file path, without touching sys.modules
    globally in a way that leaks one folder's copy into another's test."""
    if name in _loaded:
        return _loaded[name]
    path = TOOLS[name]
    spec = importlib.util.spec_from_file_location(f"igtest_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _loaded[name] = mod
    return mod
