#!/usr/bin/env python3
"""
detect.py - a five-check panel that scores how machine-written a draft looks.

What this is:  five local heuristics modelled on the signals public AI
detectors actually measure - sentence-length variation, concreteness, stock
vocabulary, typographic fingerprint, and voice. Every score is computed on
your machine from the text alone. Nothing is uploaded.

What this is NOT:  GPTZero, Originality, Copyleaks, Winston or Turnitin.
It does not call their APIs and it cannot promise their verdict. It catches
the things they all key on, which is why fixing them tends to move their
numbers too - but the only honest claim is the one on this line.

Each check returns a HUMAN score from 0 to 100. Higher is better.

Usage
  python3 detect.py draft.txt
  pbpaste | python3 detect.py -
  python3 detect.py draft.txt --json
  python3 detect.py before.txt after.txt      # compare two drafts
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))

# iOS types "’" for "'". The data spells every apostrophe straight, so the
# copy a regex or word list is matched against does too. Same length, so
# spans still line up, and the user's own text is never rewritten.
APOSTROPHES = str.maketrans("‘’", "''")
SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")
WORD_RE = re.compile(r"(?:[^\W\d_]|')+")
NUMBERS = re.compile(r"\b\d[\d,.]*%?\b|\$\d")
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]{2,}\b", re.MULTILINE)


class LexiconError(Exception):
    """The lexicon is missing, unreadable, incomplete or has a bad regex."""


class MessagesError(Exception):
    """The messages file is missing, unreadable or incomplete."""


def say(M, key, **kw):
    """One sentence from the language file's messages, with its values filled in."""
    return M[key].format(**kw)


_MESSAGES = {}                                    # code -> messages, filled on success only


def load_messages(lang="en"):
    """Every sentence this script prints: lang/<lang>.json, section "detect".
    Always follows --lang; --lexicon swaps the lexicon and nothing else."""
    if lang in _MESSAGES:
        return _MESSAGES[lang]
    path = os.path.join(HERE, "lang", lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            messages = json.load(fh)["detect"]["messages"]
        if not (isinstance(messages, dict) and all(isinstance(v, str) for v in messages.values())):
            raise TypeError(messages)
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise MessagesError(f"{path}: {type(err).__name__}: {err}") from None
    _MESSAGES[lang] = messages
    return messages


def load_lexicon(path=None, lang="en"):
    """slop.<lang>.json. `voice` holds the two voice regexes: contractions
    and personal pronouns, the words that put a person in the text."""
    path = path or os.path.join(HERE, "slop." + lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            lex = json.load(fh)
        for key in ("words", "phrases", "structures", "dependents"):
            if not isinstance(lex[key], list):
                raise TypeError(f"{key} must be a list")
        for key in ("contractions", "pronouns"):
            re.compile(lex["voice"][key])
        return lex
    except (OSError, ValueError, KeyError, TypeError, re.error) as err:
        raise LexiconError(f"{path}: {type(err).__name__}: {err}") from None


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
    """{code: stopwords} for each lexicon on disk that carries them."""
    found = {}
    for code in (c for c in LANGS if c != "auto"):
        try:
            with open(os.path.join(HERE, "slop." + code + ".json"), encoding="utf-8") as fh:
                found[code] = set(json.load(fh)["auto"]["stopwords"])
        except (OSError, ValueError, KeyError, TypeError):
            continue                              # skipped for auto; the normal load reports it
    return found


def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


def sentences(text):
    return [s.strip() for s in SENT_RE.findall(text) if len(s.split()) > 2]


def words(text):
    return WORD_RE.findall(text)


def check_burstiness(text, lang="en"):
    """Humans vary sentence length hard. Models write even."""
    M = load_messages(lang)
    lens = [len(s.split()) for s in sentences(text)]
    if len(lens) < 4:
        return 50.0, say(M, "too_short")
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    score = scale(cv, human=0.70, machine=0.22)
    return score, say(M, "burstiness_detail", variation=cv, count=len(lens))


def check_specificity(text, lang="en"):
    """Numbers, names and concrete nouns. Slop is abstract."""
    M = load_messages(lang)
    w = words(text)
    if len(w) < 25:
        return 50.0, say(M, "too_short")
    per100 = 100 / len(w)
    hits = len(NUMBERS.findall(text)) + len(set(PROPER.findall(text)))
    density = hits * per100
    score = scale(density, human=6.0, machine=0.5)
    return score, say(M, "specificity_detail", hits=hits, density=density)


def term_re(find):
    """A lexicon entry as a regex: whitespace-tolerant, whole words. The edge
    \\b only goes on an edge that is a word character: after the "?" of
    "what are your thoughts?" a \\b demands a letter, so the entry never
    matched at the end of a caption. Same function in humanize.py and detect.py."""
    lead = r"\b" if re.match(r"\w", find[0]) else ""
    trail = r"\b" if re.match(r"\w", find[-1]) else ""
    return re.compile(lead + re.escape(find).replace(r"\ ", r"\s+") + trail, re.IGNORECASE)


def check_slop(text, lex, lang="en"):
    """Stock vocabulary density against the lexicon."""
    M = load_messages(lang)
    w = words(text)
    if not w:
        return 50.0, say(M, "empty")
    hits, found = 0, []
    # Longest first, and a match is blanked out once counted, so "delve into"
    # is one stock term and not also a "delve". Same order humanize.py uses.
    entries = sorted(lex["phrases"] + lex["words"], key=lambda e: len(e["find"]), reverse=True)
    rest = text
    for entry in entries:
        pattern = term_re(entry["find"])
        n = len(pattern.findall(rest))
        if n:
            hits += n
            found.append(entry["find"])
            rest = pattern.sub(lambda m: " " * len(m.group(0)), rest)
    density = hits * 100 / len(w)
    score = scale(density, human=0.0, machine=4.0)
    detail = say(M, "slop_detail", hits=hits, density=density)
    if found:
        terms = ", ".join(sorted(found)[:4])
        if len(found) > 4:
            detail += say(M, "slop_terms_more", terms=terms)
        else:
            detail += say(M, "slop_terms", terms=terms)
    return score, detail


def check_fingerprint(text, lang="en"):
    """Characters a phone keyboard does not produce."""
    M = load_messages(lang)
    invisible = sum(1 for c in text if unicodedata.category(c) == "Cf")
    em = text.count("—")
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    nbsp = sum(text.count(c) for c in "   ")
    total = invisible * 4 + em * 2 + curly + ellip + nbsp
    per1k = total * 1000 / max(len(text), 1)
    score = scale(per1k, human=0.0, machine=12.0)
    detail = say(M, "fingerprint_detail", invisible=invisible, em=em, curly=curly,
                 ellipsis=ellip, nbsp=nbsp)
    return score, detail


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


def count_hanging(text, lex):
    """Deletions humanize.py holds back because the sentence would be left
    hanging: it keeps them for a person to rewrite, so they count as tells.
    Same walk as humanize: longest entry first, a match taken out of reach
    (a NUL run, which no dependent matches) once seen."""
    n = 0
    entries = sorted((e for e in lex["phrases"] + lex["words"] if not e["replace"]),
                     key=lambda e: len(e["find"]), reverse=True)
    for entry in entries:
        pattern = term_re(entry["find"])
        n += sum(1 for m in pattern.finditer(text) if hangs(entry["find"], text, m.end(), lex))
        text = pattern.sub(lambda m: "\x00" * len(m.group(0)), text)
    return n


def count_tells(text, lex):
    """Structural tells: the shapes humanize.py flags for a person to rewrite,
    plus the deletions it holds back ("hanging"). Returns (count, ids).
    Callable on its own (main() uses it), so it composes accents and
    straightens apostrophes itself."""
    text = unicodedata.normalize("NFC", text).translate(APOSTROPHES)
    tells, names = 0, []
    for s in lex["structures"]:
        try:
            n = len(re.compile(s["regex"], re.MULTILINE).findall(text))
        except re.error:
            continue
        if n:
            tells += n
            names.append(s["id"])
    hanging = count_hanging(text, lex)
    if hanging:
        tells += hanging
        names.append("hanging")
    return tells, names


def check_voice(text, lex, lang="en"):
    """Contractions, person, and the shapes models default to."""
    M = load_messages(lang)
    w = words(text)
    if len(w) < 25:
        return 50.0, say(M, "too_short")
    per100 = 100 / len(w)
    voice = lex["voice"]
    contractions = len(re.findall(voice["contractions"], text)) * per100
    person = len(re.findall(voice["pronouns"], text)) * per100
    tells, names = count_tells(text, lex)
    bullets = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = (len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6)
    score = (scale(contractions, human=3.0, machine=0.0) * 0.35
             + scale(person, human=8.0, machine=1.0) * 0.35
             + clamp(100 - tells * 22) * 0.30)
    if uniform:
        score -= 12
        names.append("uniform-bullets")
    detail = say(M, "voice_detail", contractions=contractions, person=person, tells=tells)
    if names:
        detail += say(M, "voice_ids", ids=", ".join(names[:4]))
    return clamp(score), detail


CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]
PASS_SCORE, CHECK_FLOOR, REVIEW_SCORE = 70, 55, 50


def scores_pass(results, overall):
    """The numbers alone would pass: overall 70+ and no check below 55."""
    return overall >= PASS_SCORE and min(r[0] for r in results.values()) >= CHECK_FLOOR


def run(text, lex, lang="en"):
    # Decomposed accents (NFD, macOS paste) split words in `re`: compose them.
    text = unicodedata.normalize("NFC", text)
    # FINGERPRINT reads the raw text: curly quotes are one of its tells.
    # Every other check matches words, so it reads the straightened copy.
    match = text.translate(APOSTROPHES)
    results = {}
    results["BURSTINESS"] = check_burstiness(match, lang)
    results["SPECIFICITY"] = check_specificity(match, lang)
    results["SLOP DENSITY"] = check_slop(match, lex, lang)
    results["FINGERPRINT"] = check_fingerprint(text, lang)
    results["VOICE"] = check_voice(match, lex, lang)
    scores = [results[c][0] for c in CHECKS]
    # The weakest check drags the verdict: a detector only needs one signal.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if scores_pass(results, overall) else (
        "REVIEW" if overall >= REVIEW_SCORE else "FLAGGED")
    # A structural tell is the part a script cannot rewrite. While one is
    # left the draft stops at REVIEW, however well the numbers came out.
    if verdict == "PASS" and count_tells(match, lex)[0]:
        verdict = "REVIEW"
    return results, overall, verdict


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render(results, overall, verdict, label=None, out=sys.stdout, tells=0, lang="en"):
    M = load_messages(lang)
    title = say(M, "panel_title_labelled", label=label) if label else say(M, "panel_title")
    print("\n" + title, file=out)
    print("=" * max(len(title), 62), file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {say(M, 'human_score_label'):<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    if verdict == "REVIEW" and scores_pass(results, overall):
        print(say(M, "held_at_review", tells=tells), file=out)
    elif verdict != "PASS":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(say(M, "weakest_signal", weakest=weakest), file=out)
    print("", file=out)


def read_text(path):
    """The input file, or stdin for "-". The file is closed before returning."""
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    ap = argparse.ArgumentParser(description="Score how machine-written a draft looks.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("compare", nargs="?", help="second file, to show before/after")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lexicon", default=None,
                    help="path to slop.<lang>.json; wins over --lang")
    ap.add_argument("--lang", choices=LANGS, default="en",
                    help="which slop.<lang>.json to use; auto picks by stopwords")
    args = ap.parse_args()

    targets = [(args.input, read_text(args.input))]
    if args.compare:
        targets.append((args.compare, read_text(args.compare)))

    lang = args.lang
    if lang == "auto" and not args.lexicon:
        lang, note = pick_lang(targets[0][1], auto_candidates())
        print(note, file=sys.stderr)
    code = "en" if lang == "auto" else lang
    try:
        lex = load_lexicon(args.lexicon, code)
    except LexiconError as err:
        print(f"detect.py: cannot load the lexicon, {err}", file=sys.stderr)
        sys.exit(2)
    try:
        load_messages(code)
    except MessagesError as err:
        print(f"detect.py: cannot load the messages, {err}", file=sys.stderr)
        sys.exit(2)

    payload = []
    for name, text in targets:
        results, overall, verdict = run(text, lex, code)
        payload.append({
            "source": name,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "human_score": round(overall, 1),
            "verdict": verdict,
            "structural_tells": count_tells(text, lex)[0],
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2, ensure_ascii=False))
    else:
        for (name, text), p in zip(targets, payload):
            results, overall, verdict = run(text, lex, code)
            render(results, overall, verdict,
                   label=os.path.basename(name) if args.compare else None,
                   tells=p["structural_tells"], lang=code)
        if args.compare:
            a, b = payload
            delta = b["human_score"] - a["human_score"]
            print(f"  {a['human_score']:.1f} {a['verdict']}  ->  "
                  f"{b['human_score']:.1f} {b['verdict']}   ({delta:+.1f})\n")

    sys.exit(0 if payload[-1]["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
