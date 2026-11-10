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


class LexiconError(Exception):
    """The lexicon is missing, unreadable, incomplete or has a bad regex."""


class MessagesError(Exception):
    """The messages file is missing, unreadable or incomplete."""


def say(M, key, **kw):
    """One sentence from the language file's messages, with its values filled in."""
    return M[key].format(**kw)


_MESSAGES = {}                                    # code -> messages, filled on success only
_CONCRETE = {}                                    # code -> build_concrete(...), same


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


def load_concrete(lang="en"):
    """What counts as concrete: lang/<lang>.json, section "concrete", shared
    with hookscore, beats and caption. Follows --lang, as the messages do."""
    if lang in _CONCRETE:
        return _CONCRETE[lang]
    path = os.path.join(HERE, "lang", lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            C = build_concrete(json.load(fh)["concrete"])
    except (OSError, ValueError, KeyError, TypeError, re.error) as err:
        raise MessagesError(f"{path}: {type(err).__name__}: {err}") from None
    _CONCRETE[lang] = C
    return C


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
    and personal pronouns, the words that put a person in the text.
    `calibrated` (absent = true, so a lexicon you wrote keeps passing) says
    whether the stock vocabulary was built from a corpus; when it is false
    the verdict never reaches PASS."""
    path = path or os.path.join(HERE, "slop." + lang + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            lex = json.load(fh)
        check_lexicon(lex)
        return lex
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise LexiconError(f"{path}: {type(err).__name__}: {err}") from None


def check_lexicon(lex):
    """Every field humanize and detect read, checked once, at load. A lexicon
    edited by hand and broken stops here with the field named (exit 2), never
    halfway through a run with a traceback, and never by quietly skipping a
    check: a structural tell whose regex does not compile used to vanish, and
    the verdict went up to PASS. Same function in humanize.py and detect.py."""
    def fail(where, what):
        raise ValueError(f"{where}: {what}")

    def text(v, where, empty=True):
        if not isinstance(v, str) or (not empty and not v):
            fail(where, "must be a string" if empty else "must be a non-empty string")

    def regex(v, where, empty=False):
        text(v, where, empty)
        try:
            re.compile(v)
        except re.error as err:
            fail(where, f"not a valid regex ({err})")

    def table(v, where):
        if not isinstance(v, dict):
            fail(where, "must be an object")
        return v

    def field(obj, key, where):
        if key not in obj:
            fail(where, f'missing "{key}"')
        return obj[key]

    table(lex, "lexicon")
    for key in ("invisible", "typographic", "words", "phrases", "structures",
                "connectives", "conjunctions", "dependents", "complementizers"):
        if not isinstance(field(lex, key, "lexicon"), list):
            fail(key, "must be a list")
    for key in ("connectives", "conjunctions", "dependents", "complementizers"):
        for i, v in enumerate(lex[key]):
            text(v, f"{key}[{i}]", empty=False)
    for i, e in enumerate(lex["invisible"]):
        at = f"invisible[{i}]"
        table(e, at)
        cp = field(e, "cp", at)
        ends = [int(c[2:], 16) for c in cp.split("-")] if (
            isinstance(cp, str)
            and re.fullmatch(r"U\+[0-9A-Fa-f]{1,6}(?:-U\+[0-9A-Fa-f]{1,6})?", cp)) else []
        if not ends or max(ends) > 0x10FFFF or ends != sorted(ends):
            fail(at + ".cp", 'must be "U+XXXX" or "U+XXXX-U+YYYY", low to high')
        text(field(e, "name", at), at + ".name")
        if field(e, "action", at) not in ("delete", "space"):
            fail(at + ".action", 'must be "delete" or "space"')
    for i, e in enumerate(lex["typographic"]):
        at = f"typographic[{i}]"
        table(e, at)
        text(field(e, "from", at), at + ".from", empty=False)
        text(field(e, "name", at), at + ".name")
        text(field(e, "to", at), at + ".to")
    for key in ("words", "phrases"):
        for i, e in enumerate(lex[key]):
            at = f"{key}[{i}]"
            table(e, at)
            text(field(e, "find", at), at + ".find", empty=False)
            text(field(e, "replace", at), at + ".replace")
            text(field(e, "family", at), at + ".family")
            roles = e.get("roles", [])
            if not isinstance(roles, list):
                fail(at + ".roles", "must be a list")
            for j, r in enumerate(roles):
                rat = f"{at}.roles[{j}]"
                table(r, rat)
                for side in ("prev", "next"):
                    if side in r:
                        regex(r[side], f"{rat}.{side}")
                if field(r, "replace", rat) is not None:
                    text(r["replace"], rat + ".replace")
    for i, s in enumerate(lex["structures"]):
        at = f"structures[{i}]"
        table(s, at)
        for key in ("id", "name", "fix"):
            text(field(s, key, at), f"{at}.{key}")
        regex(field(s, "regex", at), at + ".regex")
    voice = table(field(lex, "voice", "lexicon"), "voice")
    for key in ("contractions", "pronouns"):
        regex(field(voice, key, "voice"), "voice." + key)
    if "article" in lex:
        art = table(lex["article"], "article")
        if "vowel" in art:
            regex(art["vowel"], "article.vowel", empty=True)
        forms = table(art.get("forms", {}), "article.forms")
        for key in ("consonant", "vowel"):
            if key in forms:
                text(forms[key], "article.forms." + key)
    if not isinstance(lex.get("calibrated", True), bool):
        fail("calibrated", f"must be true or false, not {lex['calibrated']!r}")
    if "lang" in lex:
        text(lex["lang"], "lang")


def any_of(items):
    """A lexicon list as one alternation of literals. An empty list matches
    nothing: a bare "|".join gave "(?:)", which matches everywhere, so an
    empty `dependents` held every deletion. Same function in humanize.py and
    detect.py."""
    return "|".join(re.escape(x) for x in items) or r"(?!)"


LANGS = ("en", "pt-BR", "auto")
# The --json output is versioned: a program reading it checks this number.
SCHEMA = 1


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
    hits = len(concrete_marks(text, load_concrete(lang)))
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
    deps = any_of(lex["dependents"])
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
        n = len(re.compile(s["regex"], re.MULTILINE).findall(text))   # load_lexicon compiled it
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


def is_calibrated(lex):
    return lex.get("calibrated", True)


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
    # An uncalibrated lexicon cannot vouch for a draft: fail closed.
    if verdict == "PASS" and not is_calibrated(lex):
        verdict = "REVIEW"
    return results, overall, verdict


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render(results, overall, verdict, label=None, out=sys.stdout, tells=0, lang="en",
           calibrated=True, lexicon_lang=None):
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
    if verdict == "REVIEW" and scores_pass(results, overall) and tells:
        print(say(M, "held_at_review", tells=tells), file=out)
    if not calibrated:
        print(say(M, "held_uncalibrated", lang=lexicon_lang or lang), file=out)
    if verdict != "PASS" and not scores_pass(results, overall):
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(say(M, "weakest_signal", weakest=weakest), file=out)
    print("", file=out)


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
        load_concrete(code)        # loaded up front: a broken section is exit 2, not a traceback
    except MessagesError as err:
        print(f"detect.py: cannot load the messages, {err}", file=sys.stderr)
        sys.exit(2)

    payload = []
    for name, text in targets:
        results, overall, verdict = run(text, lex, code)
        payload.append({
            "schema": SCHEMA,
            "source": name,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "human_score": round(overall, 1),
            "verdict": verdict,
            "structural_tells": count_tells(text, lex)[0],
            "calibrated": is_calibrated(lex),
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2, ensure_ascii=False))
    else:
        for (name, text), p in zip(targets, payload):
            results, overall, verdict = run(text, lex, code)
            render(results, overall, verdict,
                   label=os.path.basename(name) if args.compare else None,
                   tells=p["structural_tells"], lang=code,
                   calibrated=p["calibrated"], lexicon_lang=str(lex.get("lang", code)))
        if args.compare:
            a, b = payload
            delta = b["human_score"] - a["human_score"]
            print(f"  {a['human_score']:.1f} {a['verdict']}  ->  "
                  f"{b['human_score']:.1f} {b['verdict']}   ({delta:+.1f})\n")

    sys.exit(0 if payload[-1]["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
