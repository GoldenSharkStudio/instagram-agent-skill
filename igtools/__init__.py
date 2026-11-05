"""igtools - the six tools of this repo as one Python library and one CLI.

    python3 -m igtools hookscore --hook "..." --lang pt-BR --json
    python3 -m igtools caption caption.txt --keywords "a,b" --json

    import igtools
    igtools.score_hook("You lose $400 a month on this")      # -> dict

The tools live in skills/, where a skill folder copied on its own must still
run, so this package holds none of their code: it finds each script in the
skills/ folder beside it and runs that script's own main(). The CLI takes the
script's arguments and gives the script's stdout, stderr and exit code. Each
function returns what the script prints with --json, "schema" included.

Exit 1 is a verdict (a weak hook, a caption not READY, a draft not PASS):
the function returns the dict and the verdict is in it. Exit 2 is a refusal
(language data that does not load, empty text, a path that cannot be read):
the function raises igtools.Error with the tool's message.

The functions swap sys.argv, sys.stdin, sys.stdout and sys.stderr while a
tool runs. Calls from igtools are serialised by a lock, but other threads
printing at the same time would be captured: run it from one thread, or use
the CLI. stdlib only, no network.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(os.path.dirname(HERE), "skills")
SCHEMA = 1

# tool -> (skill folder, script)
TOOLS = {
    "hookscore": ("ig-reel", "hookscore.py"),
    "beats": ("ig-reel", "beats.py"),
    "caption": ("ig-caption", "caption.py"),
    "humanize": ("ig-human", "humanize.py"),
    "detect": ("ig-human", "detect.py"),
    "swipe": ("ig-viral", "swipe.py"),
}
# library function -> tool
API = {
    "score_hook": "hookscore",
    "beat_sheet": "beats",
    "lint_caption": "caption",
    "humanize": "humanize",
    "detect": "detect",
    "rank_swipe": "swipe",
}

_modules = {}
_lock = threading.RLock()


class Error(Exception):
    """A tool refused its input. `code` is its exit code (2), `tool` its name,
    and the message is what it wrote to stderr."""

    def __init__(self, tool, code, message):
        super().__init__(message)
        self.tool, self.code = tool, code


def path_of(tool):
    folder, script = TOOLS[tool]
    return os.path.join(SKILLS, folder, script)


def load(tool):
    """The tool's script as a module, loaded once, under a private name."""
    if tool not in TOOLS:
        raise Error(tool, 2, f"igtools: no tool named {tool!r}; one of {', '.join(TOOLS)}")
    with _lock:
        if tool in _modules:
            return _modules[tool]
        path = path_of(tool)
        if not os.path.isfile(path):
            raise Error(tool, 2, f"igtools: cannot find {path}: igtools runs the tools "
                                 f"in the skills/ folder beside it")
        spec = importlib.util.spec_from_file_location(f"igtools._{tool}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _modules[tool] = mod
        return mod


def _exit_code(err):
    if err.code is None:
        return 0
    return err.code if isinstance(err.code, int) else 1


def call(tool, argv, stdin=""):
    """Run the tool's main() in this process: (exit code, stdout, stderr)."""
    mod = load(tool)
    out, err = io.StringIO(), io.StringIO()
    with _lock:
        saved = sys.argv, sys.stdin
        sys.argv, sys.stdin = [f"igtools {tool}", *argv], io.StringIO(stdin)
        code = 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    mod.main()
                except SystemExit as stop:
                    code = _exit_code(stop)
                    if not isinstance(stop.code, (int, type(None))):
                        print(stop.code, file=sys.stderr)
        finally:
            sys.argv, sys.stdin = saved
    return code, out.getvalue(), err.getvalue()


def _json(tool, argv, stdin=""):
    code, out, err = call(tool, [*argv, "--json"], stdin)
    if code not in (0, 1):
        raise Error(tool, code, err.strip() or f"igtools: {tool} exited {code}")
    return json.loads(out)


def score_hook(text, lang="en"):
    """One hook. Blank text is refused."""
    return _json("hookscore", [f"--hook={text}", f"--lang={lang}"])


def beat_sheet(script, wpm=165, target=None, lang="en"):
    argv = ["-", f"--wpm={wpm}", f"--lang={lang}"]
    if target is not None:
        argv.append(f"--target={target}")
    return _json("beats", argv, script)


def lint_caption(text, keywords=(), lang="en", truncate=None):
    """`keywords` is a list of terms; the CLI takes them comma-separated, so a
    term cannot hold a comma."""
    keywords = list(keywords)
    if any("," in k for k in keywords):
        raise ValueError("a keyword cannot hold a comma")
    argv = ["-", f"--keywords={','.join(keywords)}", f"--lang={lang}"]
    if truncate is not None:
        argv.append(f"--truncate={truncate}")
    return _json("caption", argv, text)


def humanize(text, lang="en", lexicon=None):
    """{"schema", "text", "report"}: the cleaned text and what changed."""
    argv = ["-", f"--lang={lang}"] + ([f"--lexicon={lexicon}"] if lexicon else [])
    return _json("humanize", argv, text)


def detect(text, lang="en", lexicon=None):
    argv = ["-", f"--lang={lang}"] + ([f"--lexicon={lexicon}"] if lexicon else [])
    return _json("detect", argv, text)


def rank_swipe(tsv, lang="en", hooks=None):
    """`tsv` is the captured file's text: a header row, then one reel a row."""
    argv = ["-", f"--lang={lang}"] + ([f"--hooks={hooks}"] if hooks else [])
    return _json("swipe", argv, tsv)
