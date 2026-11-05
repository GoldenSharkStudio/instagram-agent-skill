#!/usr/bin/env python3
"""
hookscore.py - score the first line of a Reel on the five things strong hooks
have in common, and rank a batch of them against each other.

What this is:  five local heuristics, computed on your machine from the text
alone. They measure properties that hooks which hold attention tend to share -
a length you can say in under three seconds, a concrete marker, something at stake,
the payload at the front rather than the back, and a viewer to aim it at.

What this is NOT:  a view predictor. It was tested against 74 real short-form
hooks, transcribed from the first three seconds of the top eight and bottom
eight performers on five channels. Separating a real hook from a deliberately
bad one it does well: AUC 0.83, and 9 of 10 written-to-be-bad hooks scored
below the real median. Separating a good creator's hits from that same
creator's misses it barely does at all: AUC 0.56, where 0.50 is a coin flip.

So use it for what it measured well. It catches greetings, preambles, hooks
with nothing concrete in them and hooks that take five seconds to say. It will
not tell you which of two decent hooks will travel, and nothing that reads text
can, because that is decided by your face, your edit, your audio and who
Instagram shows it to. Trust the retention graph over this script.

Each check returns 0 to 100. Higher is better.

Usage
  python3 hookscore.py hooks.txt              # one hook per line, ranked
  python3 hookscore.py --hook "I lost $18,000 on one missing contract."
  pbpaste | python3 hookscore.py -
  python3 hookscore.py hooks.txt --json
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(HERE, "lang")

WORD_RE = re.compile(r"(?:[^\W_]|[$%'’-])+")
# iOS types "’" for "'". The data spells every apostrophe straight, so the
# copy a regex or word list is matched against does too. Same length, so
# spans still line up, and the user's own text is never rewritten.
APOSTROPHES = str.maketrans("‘’", "''")
HASHTAG_RE = re.compile(r"(?:^|\s)(#\w+)")
# One emoji as a reader counts it: a flag pair, a keycap, or a pictograph with
# its skin tone, variation selector and ZWJ-joined parts. Text-style symbols
# (arrows, double bang, trademark, copyright) count only when U+FE0F asks for
# the emoji form. Copied in hookscore.py and caption.py; a test keeps them equal.
EMOJI_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF]{2}"
    r"|[0-9#*]\uFE0F?\u20E3"
    r"|(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A-\u23FF]"
    r"|[\u2190-\u21FF\u203C\u2049\u2122\u2139\u00A9\u00AE]\uFE0F)"
    r"[\U0001F3FB-\U0001F3FF]?\uFE0F?"
    r"(?:\u200D[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]"
    r"[\U0001F3FB-\U0001F3FF]?\uFE0F?)*")


class LangError(Exception):
    """The language file is missing, unreadable, incomplete or has a bad regex."""


_LOADED = {}                                      # code -> loaded dict, filled on success only


def say(M, key, **kw):
    """One sentence from the language file's messages, with its values filled in."""
    return M[key].format(**kw)


def build_concrete(d):
    """The `concrete` section of a language file as one regex, in four groups:
    1 a figure, with its price sign or its unit ("$7", "23h", "3,000", "9:30");
    2 a listed word (a month, a spoken number, a money word), any case;
    3 a name inside a sentence (not at a line start, not after a full stop);
    4 an acronym ("USA", "EUA"), checked against its line in concrete_marks.
    Same function in hookscore, beats, caption and detect, so the four give one
    answer to "is this concrete?" (tests/test_concrete.py keeps them equal)."""
    def alt(xs):
        return "|".join(sorted({re.escape(x) for x in xs}, key=len, reverse=True)) or r"(?!)"
    num = r"\d+(?:[.,:]\d+)*"
    unit = r"(?:\s?(?i:" + d["number_units"] + r"))?"
    listed = list(d["months"]) + list(d["spoken_numbers"]) + list(d["money_words"])
    return {
        "re": re.compile(
            r"(\$\s?" + num + unit + r"|\b" + num + unit + r")"
            r"|((?i:\b(?:" + alt(listed) + r")\b))"
            r"|((?<![.!?]\s)(?<!^)\b[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ]{2,}\b)"
            r"|(\b[A-ZÀ-ÖØ-Þ]{2,4}\b)", re.MULTILINE),
        "caps_skip": set(d["caps_skip"]),
    }


def concrete_marks(text, C):
    """(start, mark) for every concrete thing in text, in order. An acronym
    counts only on a line that is not shouting, and never one the language
    lists in caps_skip ("DM", "OK"). Same function in hookscore, beats,
    caption and detect."""
    marks = []
    for m in C["re"].finditer(text):
        if m.lastindex == 4:
            start = text.rfind("\n", 0, m.start()) + 1
            end = text.find("\n", m.end())
            line = text[start:end if end >= 0 else len(text)]
            if m.group() in C["caps_skip"] or not re.search(r"[a-zß-öø-ÿ]", line):
                continue
        marks.append((m.start(), m.group().strip()))
    return marks


def load_lang(code="en"):
    """Every word this script knows comes from lang/<code>.json.

    concrete: what counts as a concrete marker, shared with beats, caption and
      detect (build_concrete). Its spoken_numbers: spoken hooks say their
      numbers out loud ("twenty grand"), and counting only digits missed
      them. "one" and "first" stay out: they are filler far more often than
      a quantity.
    stakes: words that put something on the line. A hook with none is a
      statement; a hook with one is a reason to keep watching.
    weak_openers: openers that spend the first second saying nothing. Order
      matters, the first match is reported.
    imperatives: verbs that earn the front position.
    dealbreakers: the language's own; hashtag and emoji are added after them,
      their sentences coming from messages.
    messages: every sentence the script prints, str.format templates.
    """
    if code in _LOADED:
        return _LOADED[code]
    path = os.path.join(LANG_DIR, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            full = json.load(fh)
        d = full["hookscore"]
        messages = d["messages"]
        if not (isinstance(messages, dict) and all(isinstance(v, str) for v in messages.values())):
            raise TypeError(messages)
        loaded = {
            "MESSAGES": messages,
            "CONCRETE": build_concrete(full["concrete"]),
            "STAKES": set(d["stakes"]),
            "WEAK_OPENERS": list(d["weak_openers"]),
            "IMPERATIVES": set(d["imperatives"]),
            "ADDRESS_YOU": re.compile(d["address_you"]),
            "ADDRESS_ME": re.compile(d["address_me"]),
            # The language's own first, then the two that live in code.
            "DEALBREAKERS": [(re.compile(x["regex"]), x["message"]) for x in d["dealbreakers"]] + [
                (HASHTAG_RE, say(messages, "dealbreaker_hashtag")),
                (EMOJI_RE, say(messages, "dealbreaker_emoji")),
            ],
        }
    except (OSError, ValueError, KeyError, TypeError, re.error) as err:
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


def clamp(n):
    return max(0.0, min(100.0, n))


def words(text):
    # "$18,000" (and pt-BR "18.000", "3,5") is one word when spoken, so one word here.
    return WORD_RE.findall(re.sub(r"(?<=\d)[,.](?=\d)", "", text))


def check_length(text, L=None):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    M = (L or load_lang())["MESSAGES"]
    w = words(text)
    n = len(w)
    secs = n / 2.75                      # ~165 words per minute, spoken
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = clamp(100 - (5 - n) * 20)
    else:
        score = clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return clamp(score), say(M, "length_detail", n=n, chars=chars, secs=secs)


def check_specificity(text, L):
    """One concrete thing beats three abstract ones."""
    marks = [m for _, m in concrete_marks(text, L["CONCRETE"])]
    hits = len(marks)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(marks[:4])
    if found:
        return score, say(L["MESSAGES"], "specificity_found", hits=hits, found=found)
    return score, say(L["MESSAGES"], "specificity_none", hits=hits)


def check_stakes(text, L):
    """Tension, cost, negation. Something the viewer might lose."""
    w = [x.lower().strip("'’") for x in words(text)]
    hits = [x for x in w if x in L["STAKES"]]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text):
        markers.append(say(L["MESSAGES"], "a_price"))
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    if markers:
        detail = say(L["MESSAGES"], "stakes_found", n=n, markers=", ".join(markers[:4]))
    else:
        detail = say(L["MESSAGES"], "stakes_none", n=n)
    return clamp(score), detail


def check_frontload(text, L):
    """The interesting word cannot be in position nine."""
    M = L["MESSAGES"]
    w = words(text)
    if not w:
        return 0.0, say(M, "frontload_empty")
    low = [x.lower().strip("'’") for x in w]
    penalty = 0
    hit_opener = None
    for weak in L["WEAK_OPENERS"]:
        # Whole words: "yo" is not the start of "You", "oi" not of "oito".
        if low[:len(weak.split())] == weak.split():
            penalty, hit_opener = 30, weak
            break
    # The payload is the first stake or the first concrete marker, by word.
    marks = concrete_marks(text, L["CONCRETE"])
    firsts = [i for i, token in enumerate(low) if token in L["STAKES"]][:1]
    if marks:
        # "R$7" is one word and its marker starts at "$": that word, not the next.
        before = text[:marks[0][0]]
        firsts.append(len(words(before)) - (1 if before and words(before[-1]) else 0))
    payload = min(firsts) if firsts else None
    if payload is None:
        base = 30.0
        where = say(M, "payload_none")
    elif payload <= 3:
        base = 100.0
        where = say(M, "payload_early", position=payload + 1)
    elif payload <= 6:
        base = 70.0
        where = say(M, "payload_mid", position=payload + 1)
    else:
        base = 40.0
        where = say(M, "payload_late", position=payload + 1)
    detail = where + (say(M, "weak_opener", opener=hit_opener) if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text, L):
    """Aimed at one viewer, or floating in the air."""
    M = L["MESSAGES"]
    low = text.lower()
    w = [x.lower().strip("'’") for x in words(text)]
    if L["ADDRESS_YOU"].search(low):
        return 100.0, say(M, "address_viewer")
    if w and w[0] in L["IMPERATIVES"]:
        return 90.0, say(M, "address_imperative", opener=w[0])
    if L["ADDRESS_ME"].search(low):
        return 70.0, say(M, "address_first_person")
    return 35.0, say(M, "address_third_person")


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]

# Exit 0 only if the best hook reaches this. The --json path uses it too.
PASS_SCORE = 70


def run(text, lang="en"):
    # Decomposed accents (NFD, macOS paste) split words in `re`: compose them.
    text = unicodedata.normalize("NFC", text).translate(APOSTROPHES)
    L = load_lang(lang)
    results = {
        "LENGTH": check_length(text, L),
        "SPECIFICITY": check_specificity(text, L),
        "STAKES": check_stakes(text, L),
        "FRONTLOAD": check_frontload(text, L),
        "ADDRESS": check_address(text, L),
    }
    flags = [msg for pattern, msg in L["DEALBREAKERS"] if pattern.search(text)]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout, lang="en"):
    M = load_lang(lang)["MESSAGES"]
    print(say(M, "title"), file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {say(M, 'overall_label'):<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print(say(M, "dealbreaker_line", flag=f), file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(say(M, "weakest_property", weakest=weakest), file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout, lang="en"):
    M = load_lang(lang)["MESSAGES"]
    print(say(M, "ranking_title") + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}", file=out)
        print(say(M, "ranking_weakest", weakest=r["weakest"],
                  score=r["checks"][r["weakest"]]["score"]), file=out)
        for f in r["flags"]:
            print(say(M, "ranking_dealbreaker", flag=f), file=out)
    print(say(M, "ranking_footer", pass_score=PASS_SCORE), file=out)


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


def main():
    ap = argparse.ArgumentParser(description="Score a Reel hook on five properties.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lang", choices=LANGS, default="en",
                    help="language data to score with; auto picks by stopwords")
    args = ap.parse_args()

    if args.hook:
        lines = [args.hook]
    else:
        raw = read_text(args.input)
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    # Composed once here too: the ranking cuts long hooks by character count.
    lines = [unicodedata.normalize("NFC", l) for l in lines]

    lang, note = args.lang, None
    if lang == "auto":
        lang, note = pick_lang("\n".join(lines), auto_candidates())
    if note and lines:
        print(note, file=sys.stderr)
    try:
        L = load_lang(lang)
    except LangError as err:
        print(f"hookscore.py: cannot load language data, {err}", file=sys.stderr)
        sys.exit(2)
    if not lines:
        print(say(L["MESSAGES"], "nothing_to_score"), file=sys.stderr)
        sys.exit(2)

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line, lang)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
    elif len(payload) == 1:
        results, overall, verdict, flags = run(lines[0], lang)
        render_one(lines[0], results, overall, verdict, flags, lang=lang)
    else:
        render_table(sorted(payload, key=lambda r: -r["score"]), lang=lang)

    sys.exit(0 if max(p["score"] for p in payload) >= PASS_SCORE else 1)


if __name__ == "__main__":
    main()
