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


def hook_lang_error(lang):
    """Why hookscore cannot score in this language, or None if it can."""
    if score_hook is None:
        return None
    try:
        load_lang(lang)
    except LangError as err:
        return str(err)
    return None


def load_formulas(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    by_id = {h["id"]: h for h in d["hooks"]}
    order = d.get("classify_order") or sorted(by_id)
    return [(by_id[i]["id"], by_id[i]["name"],
             re.compile(by_id[i]["match"], re.IGNORECASE)) for i in order if i in by_id]


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
    """The input file, or stdin for "-". The file is closed before returning."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_rows(path):
    raw = unicodedata.normalize("NFC", read_text(path))
    lines = [l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        cols, body = ["account", "followers", "views", "hook"], lines
    rows = []
    for line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        try:
            r["views"] = int(re.sub(r"[^\d]", "", r.get("views", "")) or 0)
        except ValueError:
            continue
        for k in ("followers", "median"):
            digits = re.sub(r"[^\d]", "", r.get(k, "") or "")
            r[k] = int(digits) if digits else None
        if r["views"] and r.get("hook"):
            rows.append(r)
    return rows


def analyse(rows, formulas, lang="en"):
    scoring = score_hook is not None and hook_lang_error(lang) is None
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        r["formula_id"], r["formula"] = classify(r["hook"], formulas, lang)
        r["words"] = len(WORD_RE.findall(r["hook"]))
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
                  say(M, "md_hook", hook=r["hook"]), ""]
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
    ap.add_argument("--hooks", default=HOOKS, help="path to ig-reel/hooks.json")
    ap.add_argument("--out", help="also write the swipe file as markdown here")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lang", choices=LANGS, default="en",
                    help="language the hooks are scored in; auto picks by stopwords")
    args = ap.parse_args()

    rows = read_rows(args.input)
    lang = args.lang
    if lang == "auto" and not rows:
        lang = "en"                      # nothing to pick from: auto is en
    elif lang == "auto":
        lang = pick_swipe_lang(rows)
    try:
        M = load_messages(lang)
    except MessagesError as err:
        print(f"swipe.py: cannot load the messages, {err}", file=sys.stderr)
        sys.exit(2)
    if not rows:
        print(say(M, "no_rows"), file=sys.stderr)
        sys.exit(2)
    formulas = load_formulas(args.hooks)
    a = analyse(rows, formulas, lang)
    if not formulas:
        print(say(M, "note_no_formulas"), file=sys.stderr)
    if score_hook is None:
        print(say(M, "note_no_hookscore"), file=sys.stderr)
    elif hook_lang_error(lang):
        print(say(M, "note_hookscore_lang", lang=lang, reason=hook_lang_error(lang)),
              file=sys.stderr)

    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a, lang=lang)
    if args.out:
        path = os.path.expanduser(args.out)
        if os.path.dirname(path):        # a bare "swipe.md" has no folder to make
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(a, lang))
        print(say(M, "wrote", path=path), file=sys.stderr)


if __name__ == "__main__":
    main()
