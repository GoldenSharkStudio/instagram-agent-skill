#!/usr/bin/env python3
"""
humanize.py - strip the machine fingerprint out of a draft.

Three passes, in this order:

  1. INVISIBLE   delete or normalise the characters a human keyboard never
                 produces: zero-width joiners, word joiners, soft hyphens,
                 BOMs, Unicode tag characters, non-breaking and narrow spaces.
                 These survive copy-paste and are the most mechanical tell in
                 any generated text.
  2. TYPOGRAPHIC em dash -> comma, en dash -> hyphen, curly quotes -> straight,
                 ellipsis -> three dots, bullet -> hyphen.
  3. LEXICAL     replace the slop lexicon in slop.en.json with plain words,
                 preserving capitalisation and leaving URLs untouched.

Structural tells (rule-of-three, "not just X, it's Y", hashtag walls) are
REPORTED, never auto-rewritten - rewriting a sentence's shape needs judgement,
so that is the model's job, not a regex's.

Usage
  python3 humanize.py draft.txt
  python3 humanize.py draft.txt --report
  pbpaste | python3 humanize.py - --report
  python3 humanize.py draft.txt --json
  python3 humanize.py draft.txt -o clean.txt
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.en.json")

URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")


class LexiconError(Exception):
    """The lexicon is missing, unreadable or incomplete."""


def load_lexicon(path=LEX):
    """slop.<lang>.json. `connectives` are the words that, after an em dash
    turned into a comma, leave a splice worth promoting to a full stop.
    `conjunctions` are the words that go with a deleted phrase they joined.
    `dependents` open a clause that hangs on the phrase before it, so that
    phrase is kept and flagged instead of deleted; `complementizers` ("that")
    go with a deleted opener and leave the clause after them standing."""
    try:
        with open(path, encoding="utf-8") as fh:
            lex = json.load(fh)
        for key in ("invisible", "typographic", "words", "phrases", "structures",
                    "connectives", "conjunctions", "dependents", "complementizers"):
            if not isinstance(lex[key], list):
                raise TypeError(f"{key} must be a list")
        return lex
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise LexiconError(f"{path}: {type(err).__name__}: {err}") from None


def _cp(spec):
    """'U+200B' -> '\\u200b';  'U+E0000-U+E007F' -> (start, end)."""
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def protect_urls(text):
    """Swap URLs for placeholders so no pass rewrites inside a link."""
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def restore_urls(text, found):
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def pass_invisible(text, lex):
    """Delete or space-normalise invisible characters. Returns (text, hits)."""
    hits = []
    for entry in lex["invisible"]:
        cp = _cp(entry["cp"])
        if isinstance(cp, tuple):
            pattern = "[" + re.escape(chr(cp[0])) + "-" + re.escape(chr(cp[1])) + "]"
        else:
            pattern = re.escape(chr(cp))
        n = len(re.findall(pattern, text))
        if n:
            hits.append({"name": entry["cp"] + " " + entry["name"], "count": n,
                         "action": entry["action"]})
            text = re.sub(pattern, "" if entry["action"] == "delete" else " ", text)
    # Any remaining Cf (format) character is invisible by definition.
    stray = [c for c in text if unicodedata.category(c) == "Cf"]
    if stray:
        hits.append({"name": "other invisible format chars", "count": len(stray),
                     "action": "delete"})
        text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    return text, hits


def pass_typographic(text, lex):
    hits = []
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        hits.append({"name": f"{ch} {entry['name']}", "count": n, "to": entry["to"].strip() or "(space)"})
        if ch == "—":
            # " word — word " and "word—word" both collapse to a comma + space.
            text = re.sub(r"\s*—\s*", ", ", text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)      # 5–10  -> 5-10
            text = re.sub(r"\s+–\s+", ", ", text)            # used as em dash
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, entry["to"])
    # A comma inserted before existing punctuation reads wrong.
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*\n", "\n", text)
    return text, hits


def _match_case(src, repl):
    if not repl:
        return repl
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def term_re(find):
    """A lexicon entry as a regex: whitespace-tolerant, whole words. The edge
    \\b only goes on an edge that is a word character: after the "?" of
    "what are your thoughts?" a \\b demands a letter, so the entry never
    matched at the end of a caption. Same function in humanize.py and detect.py."""
    lead = r"\b" if re.match(r"\w", find[0]) else ""
    trail = r"\b" if re.match(r"\w", find[-1]) else ""
    return re.compile(lead + re.escape(find).replace(r"\ ", r"\s+") + trail, re.IGNORECASE)


def hangs(find, text, end, lex):
    """Would deleting `find`, matched in `text` up to `end`, strand a clause?
    Yes when the entry ends on a dependent ("double tap if") and words follow,
    or when a dependent follows it in the same clause ("follow for more if you
    love design"). Deleting either leaves "If you love design.", a fragment.
    A stop (. ! ? :) or a line break in between ends the clause and nothing
    hangs; a comma or a dash does not ("Follow for more, if you love design").
    Any space but a newline counts as one, so a raw draft (hard spaces, em
    dashes) reads the same as the cleaned one. Same function in humanize.py
    and detect.py."""
    if not re.match(r"\w", find[-1]):
        return False
    if find.split()[-1].lower() in lex["dependents"]:
        return bool(re.match(r"[^\S\n]+\w", text[end:]))
    deps = "|".join(re.escape(d) for d in lex["dependents"])
    sep = r"(?:[^\S\n]*[,\u2014\u2013][^\S\n]*|[^\S\n]+)"
    return bool(re.match(sep + r"(?:" + deps + r")\b", text[end:], re.IGNORECASE))


DELETED = "\x00DEL\x00"   # marks where an entry was deleted, until cleanup
KEPT = "\x00KEEP{}\x00"   # a deletion held back, out of reach of the next entries


def pass_lexical(text, lex):
    """Replace slop words and phrases. Longest first so phrases win.
    Returns (text, hits, held): `held` are the deletions not made because the
    sentence would be left hanging; they go to the report for a rewrite."""
    hits, held, kept = [], [], []
    entries = sorted(lex["phrases"] + lex["words"],
                     key=lambda e: len(e["find"]), reverse=True)
    for entry in entries:
        find = entry["find"]
        pattern = term_re(find)
        if not pattern.search(text):
            continue
        if entry["replace"]:
            hits.append({"find": find, "replace": entry["replace"],
                         "count": len(pattern.findall(text)), "family": entry["family"]})
            text = pattern.sub(lambda m: _match_case(m.group(0), entry["replace"]), text)
            continue
        counts = {"deleted": 0, "held": 0}

        def delete(m):
            if hangs(find, m.string, m.end(), lex):
                counts["held"] += 1
                kept.append(m.group(0))
                return KEPT.format(len(kept) - 1)
            counts["deleted"] += 1
            return DELETED
        text = pattern.sub(delete, text)
        if counts["deleted"]:
            hits.append({"find": find, "replace": "(deleted)",
                         "count": counts["deleted"], "family": entry["family"]})
        if counts["held"]:
            held.append({"find": find, "count": counts["held"], "family": entry["family"]})
    for i, original in enumerate(kept):
        text = text.replace(KEPT.format(i), original)
    # "that" after a deleted opener is residue; the clause after it is the
    # content ("I'm thrilled to share that we hit 10k" -> "We hit 10k").
    comp = "|".join(re.escape(c) for c in lex["complementizers"])
    text = re.sub(DELETED + r"[ \t]+(?:" + comp + r")\b(?!')[ \t]*",
                  DELETED, text, flags=re.IGNORECASE)
    # A conjunction that joined a deleted phrase to the sentence goes with it
    # ("today and follow for more." left "today and."). Only one touching a
    # deletion: the writer's own "I think so." is not residue.
    conj = "|".join(re.escape(c) for c in lex["conjunctions"])
    text = re.sub(r"[ \t]*,?[ \t]*\b(?:" + conj + r")[ \t]+(?=" + DELETED + ")",
                  "", text, flags=re.IGNORECASE)
    # A line that was nothing but deleted phrases goes whole, newline too.
    # Left alone it keeps its end mark ("!"), which the joins below would
    # glue onto the line above, or a blank line the writer never wrote.
    text = re.sub(r"(?m)^(?:[ \t,]*" + DELETED + r")+[ \t,.;:!?]*(?:\n|$)", "", text)
    text = text.replace(DELETED, "")
    # Clean up after deletions. Deleting a whole clause leaves orphaned
    # punctuation behind ("system. ." or a line that now opens on a comma),
    # and that reads worse than the slop did.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?m)^[ \t]*(?:[,.;:]+[ \t]*)+", "", text)
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)       # one space left by a deletion.
                                                      # Deeper indents are deliberate.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r",\s*([,.;:!?])", r"\1", text)      # an em dash became a comma,
                                                      # then the clause after it went
    text = text.replace("...", "\x00ELL\x00")          # protect real ellipses
    text = re.sub(r"\.\s*\.+", ".", text)
    text = re.sub(r"([!?])\s*\.", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # An em dash that became a comma, followed by a sentence connective, leaves
    # a splice ("is important, also, it's proof"). Promote it to a full stop.
    connectives = "|".join(re.escape(c) for c in lex["connectives"])
    text = re.sub(r",\s*(" + connectives + r")\s*,\s*",
                  lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)
    return text, hits, held


def hanging_flags(held):
    """Held deletions, in the shape of a structural flag: a person rewrites them."""
    return [{"name": f'Deleting "{h["find"]}" would leave the sentence hanging',
             "count": h["count"],
             "fix": "Rewrite the sentence without the phrase. Deleting it alone "
                    "leaves a fragment (\"If you love design.\")."} for h in held]


def scan_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        found = pattern.findall(text)
        if found:
            flags.append({"name": s["name"], "count": len(found), "fix": s["fix"]})
    # Sentence-length uniformity is structural too.
    lens = [len(s.split()) for s in SENT_RE.findall(text) if len(s.split()) > 2]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        var = sum((n - mean) ** 2 for n in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        if cv < 0.35:
            flags.append({
                "name": f"Uniform sentence length (variation {cv:.2f})",
                "count": len(lens),
                "fix": "Break one sentence in half. Let another run long. Machines write even.",
            })
    return flags


def restore_capitals(original, text):
    """Deleting an opener leaves the next word lower case.

    Only fix it for writers who capitalise their sentences in the first place:
    a deliberately lower-case voice is a style, not an artefact, and shouting
    over it would be exactly the kind of thing this script exists to stop.
    """
    starts = re.findall(r"(?:^|[.!?]\s+|\n)\s*([^\W\d_])", original)
    if not starts or sum(1 for c in starts if c.isupper()) * 2 < len(starts):
        return text
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))\s*([a-zß-öø-ÿ])",
                  lambda m: m.group(0)[:-1] + m.group(1).upper(), text)


def humanize(text, lex):
    # Decomposed accents (NFD, macOS paste) split words in `re`: compose them.
    # Canonically equivalent, so the reader sees the same text.
    text = unicodedata.normalize("NFC", text)
    raw_for_case = text
    text, urls = protect_urls(text)
    text, inv = pass_invisible(text, lex)
    text, typo = pass_typographic(text, lex)
    text, lexi, held = pass_lexical(text, lex)
    text = restore_capitals(raw_for_case, text)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "invisible": inv,
        "typographic": typo,
        "lexical": lexi,
        "structures": hanging_flags(held) + scan_structures(text, lex),
    }


def render_report(report, out=sys.stderr):
    def head(title):
        print(f"\n{title}\n" + "-" * len(title), file=out)

    total = sum(h["count"] for h in report["invisible"]) \
        + sum(h["count"] for h in report["typographic"]) \
        + sum(h["count"] for h in report["lexical"])

    head("HUMANIZE REPORT")
    print(f"{total} machine artefacts removed, "
          f"{len(report['structures'])} structural tells flagged for rewrite", file=out)

    if report["invisible"]:
        head("1. INVISIBLE CHARACTERS")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. TYPOGRAPHY")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['to']}", file=out)
    if report["lexical"]:
        head("3. SLOP LEXICON")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  {h['find']}  -> {h['replace']}   [{h['family']}]", file=out)
    if report["structures"]:
        head("4. STRUCTURAL TELLS  (not auto-fixed - rewrite these yourself)")
        for h in report["structures"]:
            print(f"  {h['count']:>3}x  {h['name']}\n        {h['fix']}", file=out)
    if not any(report.values()):
        head("CLEAN")
        print("  Nothing to strip.", file=out)
    print("", file=out)


def read_text(path):
    """The input file, or stdin for "-". The file is closed before returning."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    ap = argparse.ArgumentParser(description="Strip the machine fingerprint out of a draft.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("-o", "--out", help="write cleaned text here instead of stdout")
    ap.add_argument("--report", action="store_true", help="print what changed, to stderr")
    ap.add_argument("--json", action="store_true", help="emit {text, report} as JSON")
    ap.add_argument("--lexicon", default=LEX, help="path to slop.<lang>.json")
    args = ap.parse_args()

    raw = read_text(args.input)
    try:
        lex = load_lexicon(args.lexicon)
    except LexiconError as err:
        print(f"humanize.py: cannot load the lexicon, {err}", file=sys.stderr)
        sys.exit(2)
    clean, report = humanize(raw, lex)

    if args.json:
        print(json.dumps({"text": clean, "report": report}, indent=2, ensure_ascii=False))
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(clean)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(clean)
    if args.report:
        render_report(report)


if __name__ == "__main__":
    main()
