#!/usr/bin/env python3
"""
beats.py - turn a Reel script into a timed beat sheet before you record it.

Estimates how long each line takes to say, stacks them into timecodes, and
flags the four things that kill a Reel in the edit: a hook that runs past the
three-second mark, a beat long enough for the viewer to leave, a run of lines
with nothing concrete in them, and a total length that does not match what you
said you were making.

The timings are an estimate from word count at a words-per-minute rate. They
are close enough to plan an edit and not a substitute for recording it. Set
your own rate with --wpm once you have timed yourself reading a script out
loud: most people land between 150 and 200, and the default here is 165.

Usage
  python3 beats.py script.txt
  python3 beats.py script.txt --target 30
  python3 beats.py script.txt --wpm 185 --target 45
  pbpaste | python3 beats.py -
  python3 beats.py script.txt --json
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(HERE, "lang")

WORD_RE = re.compile(r"(?:[^\W_]|[$%'’-])+")
# iOS types "’" for "'". The data spells every apostrophe straight, so the
# copy a regex or word list is matched against does too. Same length, so
# spans still line up, and the user's own text is never rewritten.
APOSTROPHES = str.maketrans("‘’", "''")
SENT_RE = re.compile(r"[^.!?]+[.!?]*")
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)\b[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]{2,}\b", re.MULTILINE)


class LangError(Exception):
    """The language file is missing, unreadable or incomplete."""


_LOADED = {}                                      # code -> loaded dict, filled on success only


def load_lang(code="en"):
    """stopwords: words too common to count as the hook coming back at the end."""
    if code in _LOADED:
        return _LOADED[code]
    path = os.path.join(LANG_DIR, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)["beats"]
        loaded = {"STOPWORDS": set(d["stopwords"])}
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise LangError(f"{path}: {type(err).__name__}: {err}") from None
    _LOADED[code] = loaded
    return loaded


LANGS = ("en", "pt-BR", "auto")


def pick_lang(text, candidates):
    """candidates: {code: set of stopwords}. Returns (code, note): the language
    whose function words the text uses most. A tie, or nothing to compare, is "en"."""
    # Composed first: a decomposed "você" would split into "vo" + "c".
    text = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    tokens = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text)
    counts = {c: sum(t in sw for t in tokens) for c, sw in candidates.items()}
    best = max(counts.values(), default=0)
    leaders = [c for c, n in counts.items() if n == best]
    if len(counts) < 2:
        return "en", "lang: auto -> en (no other language on disk)"
    code = leaders[0] if len(leaders) == 1 else "en"
    order = sorted(counts, key=lambda c: (c != code, c))
    shown = " vs ".join(str(counts[c]) for c in order)
    return code, f"lang: auto -> {code} ({'tie, ' if len(leaders) > 1 else ''}{shown})"


def auto_candidates():
    """{code: stopwords} for each language file on disk that carries them."""
    found = {}
    for code in (c for c in LANGS if c != "auto"):
        try:
            with open(os.path.join(LANG_DIR, f"{code}.json"), encoding="utf-8") as fh:
                found[code] = set(json.load(fh)["auto"]["stopwords"])
        except (OSError, ValueError, KeyError, TypeError):
            continue                              # skipped for auto; the normal load reports it
    return found


HOOK_WINDOW = 3.0        # seconds. Past this, the thumb has already decided.
MAX_BEAT = 4.0           # seconds on one idea with no change on screen.
ABSTRACT_RUN = 3         # beats in a row with nothing checkable in them.


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text.translate(APOSTROPHES)))


def pretty(token):
    """Put the thousands separator back for display."""
    return re.sub(r"(\d)(?=(\d{3})+$)", r"\1,", token)


def tc(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def split_beats(raw, wps):
    """One line is one beat, unless a line is too long to be one."""
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line:
            continue
        if len(words(line)) / wps <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        # Long paragraph: break it at sentence ends so the timings mean
        # something, and let the report say it was split.
        parts = [p.strip() for p in SENT_RE.findall(line) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and len(words(candidate)) / wps > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def num(x):
    """A number as the user typed it: 150, not 150.0; 172.5 stays 172.5."""
    return f"{x:g}"


def analyse(raw, wpm=165, target=None, lang="en"):
    # Decomposed accents (NFD, macOS paste) split words in `re`: compose them.
    raw = unicodedata.normalize("NFC", raw)
    stopwords = load_lang(lang)["STOPWORDS"]
    wps = wpm / 60.0
    beats = split_beats(raw, wps)
    if not beats:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        n = len(words(text))
        dur = n / wps
        rows.append({
            "n": i + 1,
            "start": round(clock, 2),
            "dur": round(dur, 2),
            "words": n,
            "text": text,
            "concrete": len(CONCRETE_RE.findall(text)),
            "label": "",
            "flags": [],
        })
        clock += dur
    total = clock

    # Label the structural positions a Reel is actually built around.
    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"hook runs {rows[0]['dur']:.1f}s, past the {HOOK_WINDOW:.0f}s mark")
        notes.append(f"Beat 1 takes {rows[0]['dur']:.1f}s to say. Cut it to "
                     f"{int(HOOK_WINDOW * wps)} words or fewer, or the hook lands after "
                     "the decision has been made.")
    if rows[0]["concrete"] == 0:
        notes.append("Beat 1 has no number and no name in it. Hooks without something "
                     "checkable are the ones that get scrolled.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"{r['dur']:.1f}s on one beat")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"Beat(s) {', '.join(map(str, long_beats))} run past {MAX_BEAT:.0f}s. "
                     "Either split the line or change what is on screen inside it. "
                     "A static frame is where people leave.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"Beats {start}-{r['n']} have nothing concrete in them. "
                             "Put a number, a name or a price in one of them.")
        else:
            run, start = 0, None

    # Does the last line hand you back to the first one?
    first = {w.lower() for w in words(rows[0]["text"]) if w.lower() not in stopwords}
    last = {w.lower() for w in words(rows[-1]["text"]) if w.lower() not in stopwords}
    loop = sorted(pretty(w) for w in first & last)
    if loop:
        notes.append(f"Loops: the last beat repeats \"{', '.join(loop[:3])}\" from the hook. "
                     "Second watches are free reach.")
    else:
        notes.append("No loop. The last beat shares no word with the hook, so the video "
                     "ends flat. Echoing one word from beat 1 is the cheapest replay you get.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"Length is on target ({total:.1f}s against {num(target)}s).")
        elif delta > 0:
            notes.append(f"{delta:.1f}s over target. Cut about {int(delta * wps)} words.")
        else:
            notes.append(f"{-delta:.1f}s under target. Either add {int(-delta * wps)} words "
                         "or shoot it short. Short is usually right.")

    return {
        "wpm": wpm, "target": target,
        "total_seconds": round(total, 2),
        "total_words": sum(r["words"] for r in rows),
        "beats": rows,
        "notes": notes,
    }


def render(a, out=sys.stdout):
    head = (f"BEAT SHEET  ·  {a['total_words']} words  ·  ~{a['total_seconds']:.1f}s "
            f"at {num(a['wpm'])} wpm" + (f"  ·  target {num(a['target'])}s" if a["target"] else ""))
    print("\n" + head, file=out)
    print("=" * max(len(head), 72), file=out)
    # The label column fits the widest label plus a space ("HOOK/CTA" is 8).
    width = max([8] + [len(r["label"]) + 1 for r in a["beats"]])
    for r in a["beats"]:
        label = f"{r['label']:<{width}}"
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}{r['text']}", file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<{width}}^ {f}", file=out)
    print("-" * max(len(head), 72), file=out)
    for n in a["notes"]:
        print(f"  - {n}", file=out)
    print("", file=out)


def read_text(path):
    """The input file, or stdin for "-". The file is closed before returning."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    ap = argparse.ArgumentParser(description="Time a Reel script into a beat sheet.")
    ap.add_argument("input", nargs="?", default="-", help="script file, or - for stdin")
    ap.add_argument("--wpm", type=float, default=165, help="speaking rate (default 165)")
    ap.add_argument("--target", type=float, help="target length in seconds")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lang", choices=LANGS, default="en",
                    help="language data to use; auto picks by stopwords")
    args = ap.parse_args()

    raw = read_text(args.input)
    lang = args.lang
    if lang == "auto":
        lang, note = pick_lang(raw, auto_candidates())
        print(note, file=sys.stderr)
    try:
        a = analyse(raw, wpm=args.wpm, target=args.target, lang=lang)
    except LangError as err:
        print(f"beats.py: cannot load language data, {err}", file=sys.stderr)
        sys.exit(2)
    if not a:
        print("empty script", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a)
    sys.exit(0)


if __name__ == "__main__":
    main()
