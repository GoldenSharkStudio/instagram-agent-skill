#!/usr/bin/env python3
"""
swipe.py - rank reels you collected by how far they beat their own account,
name the hook formula each one used, and write the swipe file.

The point of this script is one correction: raw views are not evidence. A
2,000,000-follower account doing 400,000 views had a quiet day. A 4,000-
follower account doing 400,000 views found something. This ranks on the
multiple over the account's own baseline, which is the only version of
"went viral" that tells you anything you can copy.

Input is a tab-separated file you fill in while you browse, one reel per row,
with a header line naming the columns:

    account   followers   median   views    hook
    @someone  48000       11000    412000   nobody tells you your first 30 flop

`median` is that account's typical recent views and is the better baseline.
If you only have `followers`, leave median out and the script says so.
`hook` is the first line of the reel, spoken or on screen, in their words.

Usage
  python3 swipe.py captured.tsv
  python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
  python3 swipe.py captured.tsv --json
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "ig-reel", "hooks.json")
# iOS types "’" for "'". The data spells every apostrophe straight, so the
# copy a regex or word list is matched against does too. Same length, so
# spans still line up, and the user's own text is never rewritten.
APOSTROPHES = str.maketrans("‘’", "''")
WORD_RE = re.compile(r"(?:[^\W_]|[$%'’-])+")

try:                                              # optional: score the hooks too
    sys.path.insert(0, os.path.join(HERE, "..", "ig-reel"))
    from hookscore import (run as score_hook, load_lang, LangError,   # noqa: E402
                           pick_lang, auto_candidates)
except Exception:                                 # ig-viral copied on its own
    score_hook = None

LANGS = ("en", "pt-BR", "auto")
# The --json output is versioned: a program reading it checks this number.
SCHEMA = 1


class MessagesError(Exception):
    """The messages file is missing, unreadable or incomplete."""


def say(M, key, **kw):
    """One sentence from the language file's messages, with its values filled in."""
    return M[key].format(**kw)


_MESSAGES = {}                                    # code -> messages, filled on success only


def load_messages(lang="en"):
    """Every sentence this script prints: lang/<lang>.json, section "swipe".
    Always follows --lang; --lexicon swaps the lexicon and nothing else."""
    if lang in _MESSAGES:
        return _MESSAGES[lang]
    path = os.path.join(HERE, "lang", lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            messages = json.load(fh)["swipe"]["messages"]
        if not (isinstance(messages, dict) and all(isinstance(v, str) for v in messages.values())):
            raise TypeError(messages)
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise MessagesError(f"{path}: {type(err).__name__}: {err}") from None
    _MESSAGES[lang] = messages
    return messages


_CTA = {}                                         # code -> compiled patterns


def load_cta(lang="en"):
    """The call-to-action patterns of lang/<lang>.json, section "swipe.cta".
    A captured "hook" that matches is a CTA or a row of hashtags: on that reel
    the hook is on the cover. Missing or broken list raises MessagesError."""
    if lang in _CTA:
        return _CTA[lang]
    path = os.path.join(HERE, "lang", lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)["swipe"]["cta"]
        if not (isinstance(raw, list) and raw and all(isinstance(p, str) and p for p in raw)):
            raise TypeError(raw)
        compiled = [re.compile(p, re.IGNORECASE) for p in raw]
    except (OSError, ValueError, KeyError, TypeError, re.error) as err:
        raise MessagesError(f"{path}: {type(err).__name__}: {err}") from None
    _CTA[lang] = compiled
    return compiled


def is_cta(hook, lang="en"):
    """True when the captured line is a call to action, not a hook."""
    hook = unicodedata.normalize("NFC", hook).translate(APOSTROPHES)
    return any(p.search(hook) for p in load_cta(lang))


def hook_lang_error(lang):
    """Why hookscore cannot score in this language, or None if it can."""
    if score_hook is None:
        return None
    try:
        load_lang(lang)
    except LangError as err:
        return str(err)
    return None


class HooksError(Exception):
    pass


def match_for(match, lang):
    """The regex of `lang` in a formula's `match`, or "" for none. `match` is
    {"<lang>": regex}; a plain string is a hooks.json from before the split and
    is English only. Another language's regex is never borrowed: fail closed."""
    if isinstance(match, str):
        match = {"en": match}
    if not isinstance(match, dict):
        raise TypeError(f"match must be an object of language -> regex, got {match!r}")
    for code, rx in match.items():
        if code not in LANGS or code == "auto":
            raise ValueError(f"unknown language {code!r} in match")
        if not isinstance(rx, str):
            raise TypeError(f"match[{code!r}] must be a string, got {rx!r}")
        if rx:
            re.compile(rx, re.IGNORECASE)            # every slot must compile, used or not
    return match.get(lang, "")


def load_formulas(path, lang="en"):
    """hooks.json as (id, name, compiled match of `lang`), in classify order.
    A formula with no regex in `lang` is left out, so it never matches. A file
    that cannot be read, or whose schema is broken, raises HooksError naming why."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        by_id = {h["id"]: h for h in d["hooks"]}
        order = d.get("classify_order") or sorted(by_id)
        out = []
        for i in order:
            if i in by_id:
                rx = match_for(by_id[i]["match"], lang)
                if rx:
                    out.append((by_id[i]["id"], by_id[i]["name"], re.compile(rx, re.IGNORECASE)))
        return out
    except (OSError, ValueError, KeyError, TypeError, AttributeError, re.error) as err:
        raise HooksError(f"{type(err).__name__}: {getattr(err, 'strerror', None) or err}") from None


def classify(hook, formulas, lang="en"):
    if not formulas:
        return None, say(load_messages(lang), "unclassified")
    # Decomposed accents (NFD, macOS paste) split words in `re`: compose them.
    hook = unicodedata.normalize("NFC", hook).translate(APOSTROPHES)
    for fid, name, pattern in formulas:
        if pattern.search(hook):
            return fid, name
    return None, say(load_messages(lang), "unclassified")


def read_text(path):
    """The input file, or stdin for "-". The file is closed before returning.
    A file that cannot be read is exit 2 naming it: exit 1 is a verdict."""
    try:
        if path == "-":
            return sys.stdin.read()
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as err:
        why = err.strerror if isinstance(err, OSError) and err.strerror else str(err)
        shown = "stdin" if path == "-" else path
        print(f"{os.path.basename(__file__)}: cannot read {shown}: {why}", file=sys.stderr)
        sys.exit(2)


# The cells swipe reads as numbers. Each goes through parse_count, and only it.
COUNT_COLUMNS = ("views", "followers", "median")


class CountError(Exception):
    """A count cell that does not read as a count: (line, column, cell)."""


_UNITS = {}                                       # code -> {suffix: multiplier}


def load_units(lang="en"):
    """The count suffixes of lang/<lang>.json, section "swipe.units", as the
    screen shows them ("412K", "1,2 mi"): {suffix: multiplier}, read without
    case. One table per language, no borrowing. Missing or broken raises
    MessagesError."""
    if lang in _UNITS:
        return _UNITS[lang]
    path = os.path.join(HERE, "lang", lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)["swipe"]["units"]
        if not (isinstance(raw, dict) and raw
                and all(isinstance(k, str) and re.fullmatch(r"[^\W\d_]+", k) for k in raw)
                and all(type(v) is int and v > 1 for v in raw.values())):
            raise TypeError(raw)
        units = {k.lower(): v for k, v in raw.items()}
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise MessagesError(f"{path}: {type(err).__name__}: {err}") from None
    _UNITS[lang] = units
    return units


def parse_count(cell, units):
    """A count as a person copies it, or ValueError. With a suffix the last
    "." or "," is the decimal point ("1.2M", "1,2 mi"); without one a count is
    whole, so "." and "," only group thousands ("48,000", "1.234.567") and
    "1,5" or "1e5" are not counts. A number nobody can be sure of is refused,
    never guessed: it would go to swipe.md as if it were measured."""
    m = re.fullmatch(r"(\d[\d.,]*)[ \t\u00a0\u202f]*([^\W\d_]*)", cell.strip())
    if not m:
        raise ValueError(cell)
    number, suffix = m.groups()
    if not suffix:
        if not re.fullmatch(r"\d+|\d{1,3}([.,])\d{3}(?:\1\d{3})*", number):
            raise ValueError(cell)
        return int(re.sub(r"[.,]", "", number))
    if suffix.lower() not in units:
        raise ValueError(cell)
    whole = re.fullmatch(r"(\d+|\d{1,3}(?:([.,])\d{3})+)(?:[.,](\d+))?", number)
    if not whole or (whole.group(2) and number[len(whole.group(1)):][:1] == whole.group(2)):
        raise ValueError(cell)
    digits = re.sub(r"[.,]", "", whole.group(1)) + "." + (whole.group(3) or "0")
    return round(float(digits) * units[suffix.lower()])


def read_cells(path):
    """(line number, row) for each row with a views cell and a hook, cells as
    written. The counts are read by count_rows, once the language is known."""
    raw = unicodedata.normalize("NFC", read_text(path))
    lines = [(n, l) for n, l in enumerate(raw.splitlines(), 1)
             if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0][1].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        cols, body = ["account", "followers", "views", "hook"], lines
    rows = []
    for n, line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        if r.get("views") and r.get("hook"):
            rows.append((n, r))
    return rows


def count_rows(cells, units):
    """Rows from read_cells with every count read. An empty followers or
    median is no number; a cell that is not a count raises CountError, and
    nothing is ranked."""
    out = []
    for line, r in cells:
        for k in COUNT_COLUMNS:
            cell = r.get(k) or ""
            if not cell:
                r[k] = None
                continue
            try:
                r[k] = parse_count(cell, units)
            except ValueError:
                raise CountError(line, k, cell) from None
        if r["views"]:
            out.append(r)
    return out


def read_rows(path, lang="en"):
    """The rows of a captured TSV, counts read in `lang`."""
    return count_rows(read_cells(path), load_units(lang))


def analyse(rows, formulas, lang="en"):
    scoring = score_hook is not None and hook_lang_error(lang) is None
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        r["formula_id"], r["formula"] = classify(r["hook"], formulas, lang)
        r["words"] = len(WORD_RE.findall(r["hook"]))
        r["cta"] = is_cta(r["hook"], lang)
        if scoring:
            _, overall, verdict, _ = score_hook(r["hook"], lang=lang)
            r["hook_score"], r["hook_verdict"] = round(overall, 1), verdict
        else:
            r["hook_score"], r["hook_verdict"] = None, None
    ranked = sorted(rows, key=lambda r: -(r["outlier"] or 0))
    third = max(1, len(ranked) // 3)
    top, bottom = ranked[:third], ranked[-third:]

    def med(items, key):
        vals = [i[key] for i in items if i.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    counts = {}
    for r in top:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    return {
        "baseline": "account median" if used_median else "follower count",
        "n": len(ranked),
        "accounts": len({r.get("account", "") for r in ranked}),
        "reels": ranked,
        "top_formulas": sorted(counts.items(), key=lambda kv: -kv[1]),
        "top_hook_score": med(top, "hook_score"),
        "bottom_hook_score": med(bottom, "hook_score"),
        "top_words": med(top, "words"),
        "bottom_words": med(bottom, "words"),
        "unclassified": sum(1 for r in ranked if r["formula_id"] is None),
        "cta": sum(1 for r in ranked if r["cta"]),
    }


def render(a, out=sys.stdout, lang="en"):
    M = load_messages(lang)
    head = say(M, "head", n=a["n"], accounts=a["accounts"], baseline=a["baseline"])
    print("\n" + head, file=out)
    print("=" * max(len(head), 78), file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        print(say(M, "reel_line", mult=mult, score=score, fid=fid, formula=r["formula"][:22],
                  account=r.get("account", "")[:16], views=r["views"]), file=out)
        print(f"           \"{r['hook'][:96]}\"", file=out)
        if r["cta"]:
            print(say(M, "cta_mark"), file=out)
    print("-" * max(len(head), 78), file=out)
    print(say(M, "working_title"), file=out)
    if a["top_formulas"]:
        top = ", ".join(say(M, "formula_count", name=n, count=c) for n, c in a["top_formulas"][:4])
        print(say(M, "top_formulas", formulas=top), file=out)
    if a["top_hook_score"] is not None:
        print(say(M, "median_score", top=a["top_hook_score"], bottom=a["bottom_hook_score"]),
              file=out)
    print(say(M, "median_length", top=a["top_words"], bottom=a["bottom_words"]), file=out)
    print(say(M, "unclassified_line", count=a["unclassified"], n=a["n"]), file=out)
    if a["cta"]:                         # no CTA, no line: a clean batch prints as before
        print(say(M, "cta_line", count=a["cta"], n=a["n"]), file=out)
    print(say(M, "caveat"), file=out)


def to_markdown(a, lang="en"):
    M = load_messages(lang)
    lines = [say(M, "md_title"), "",
             say(M, "md_summary", n=a["n"], accounts=a["accounts"], baseline=a["baseline"]), ""]
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "?"
        lines += [say(M, "md_reel", mult=mult, formula=r["formula"], account=r.get("account", "")),
                  say(M, "md_views", views=r["views"], baseline=r["baseline"]),
                  say(M, "md_score", score=r["hook_score"], words=r["words"]),
                  say(M, "md_hook", hook=r["hook"])]
        if r["cta"]:
            lines.append(say(M, "md_cta"))
        lines.append("")
    return "\n".join(lines) + "\n"


def pick_swipe_lang(rows):
    """--lang auto: the language of all the hooks together, by hookscore's data."""
    if score_hook is None:
        print("lang: auto -> en (hookscore.py not importable, nothing to compare)",
              file=sys.stderr)
        return "en"
    code, note = pick_lang("\n".join(r["hook"] for r in rows), auto_candidates())
    print(note, file=sys.stderr)
    return code


def main():
    ap = argparse.ArgumentParser(description="Rank collected reels by outlier multiple.")
    ap.add_argument("input", nargs="?", default="-", help="TSV file, or - for stdin")
    ap.add_argument("--hooks", default=None,
                    help="path to ig-reel/hooks.json (default: the copy next to this folder)")
    ap.add_argument("--out", help="also write the swipe file as markdown here")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lang", choices=LANGS, default="en",
                    help="language the hooks are scored in; auto picks by stopwords")
    args = ap.parse_args()

    cells = read_cells(args.input)
    lang = args.lang
    if lang == "auto" and not cells:
        lang = "en"                      # nothing to pick from: auto is en
    elif lang == "auto":
        lang = pick_swipe_lang([r for _, r in cells])
    try:
        M = load_messages(lang)
        load_cta(lang)
        units = load_units(lang)
    except MessagesError as err:
        print(f"swipe.py: cannot load the messages, {err}", file=sys.stderr)
        sys.exit(2)
    try:
        rows = count_rows(cells, units)
    except CountError as err:
        line, column, cell = err.args
        print(say(M, "bad_count", path="stdin" if args.input == "-" else args.input,
                  line=line, column=column, cell=cell), file=sys.stderr)
        sys.exit(2)
    if not rows:
        print(say(M, "no_rows"), file=sys.stderr)
        sys.exit(2)
    try:
        formulas = load_formulas(args.hooks or HOOKS, lang)
    except HooksError as err:
        if args.hooks:                   # asked for by name: a bad path is exit 2, not a result
            print(say(M, "cannot_load_hooks", path=args.hooks, reason=err), file=sys.stderr)
            sys.exit(2)
        formulas = None                  # the default copy: ig-viral alone degrades
    a = analyse(rows, formulas, lang)
    if formulas is None:
        print(say(M, "note_no_formulas"), file=sys.stderr)
    elif not formulas:                   # loaded, but nothing written for this language
        print(say(M, "note_no_formulas_lang", lang=lang), file=sys.stderr)
    if score_hook is None:
        print(say(M, "note_no_hookscore"), file=sys.stderr)
    elif hook_lang_error(lang):
        print(say(M, "note_hookscore_lang", lang=lang, reason=hook_lang_error(lang)),
              file=sys.stderr)

    if args.json:
        print(json.dumps({"schema": SCHEMA, **a}, indent=2, ensure_ascii=False))
    else:
        render(a, lang=lang)
    if args.out:
        path = os.path.expanduser(args.out)
        try:
            if os.path.dirname(path):    # a bare "swipe.md" has no folder to make
                os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(to_markdown(a, lang))
        except OSError as err:           # exit 1 is a verdict; a bad path is 2
            print(say(M, "cannot_write", path=path, reason=err.strerror or err), file=sys.stderr)
            sys.exit(2)
        print(say(M, "wrote", path=path), file=sys.stderr)


if __name__ == "__main__":
    main()
