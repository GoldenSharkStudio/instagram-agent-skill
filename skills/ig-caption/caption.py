#!/usr/bin/env python3
"""
caption.py - lint an Instagram caption and show exactly what the feed shows
before the "... more".

Instagram gives a caption about 125 characters in the feed and hides the rest
behind a tap. Almost every caption that fails, fails there: the hook is in
sentence three, or the first line is a greeting, or the whole thing opens on a
hashtag. This prints the visible window as a box so you can read it the way a
scrolling stranger does, then checks the eight things that are worth checking.

The 125-character cut is an approximation. The real number moves with the
device, the font size and where your line breaks fall, which is exactly why
you want a margin rather than a caption engineered to end at 125. Change it
with --truncate if you want to test a tighter one.

Usage
  python3 caption.py caption.txt
  python3 caption.py caption.txt --keywords "proposal software,client contract"
  pbpaste | python3 caption.py -
  python3 caption.py caption.txt --json
"""

import argparse
import json
import os
import re
import sys
import textwrap
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(HERE, "lang")

LIMIT = 2200             # Instagram's hard caption limit.
TRUNCATE = 125           # Roughly where the feed cuts to "... more".
FEED_WIDTH = 52          # Columns of the feed box. The two bottom-border messages
                         # (feed_more, feed_whole) are drawn for this width.
HASHTAG_LIMIT = 5        # Instagram's cap per post or reel since 18 Dec 2025,
                         # down from 30. Announced by the @Creators account:
                         # "using fewer (up to 5) more targeted hashtags,
                         # rather than many generic ones, can improve both your
                         # content's performance and people's experience".

# iOS types "’" for "'". The data spells every apostrophe straight, so the
# copy a regex or word list is matched against does too. Same length, so
# spans still line up, and the user's own text is never rewritten.
APOSTROPHES = str.maketrans("‘’", "''")
HASHTAG_RE = re.compile(r"(?:^|\s)(#\w+)")
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
# A bare domain needs a path to count ("Vendas.com" is a word), and may end in
# a country code ("loja.com.br/x"). Same bare-domain part in humanize URL_RE;
# tests/test_links.py runs every link regex on the same links.
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|co|io|net|org|ai|app)(?:\.[a-z]{2})?/\S*",
                     re.IGNORECASE)
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
    """concrete: what counts as a concrete marker, shared with hookscore,
    beats and detect (build_concrete).
    asks: the calls to action ONE ASK counts, each a regex, a name to print
    and an id, the same in every language (the --json `ask_ids`).
    filler_tags: hashtags so generic they describe nothing.
    messages: every sentence the script prints, str.format templates."""
    if code in _LOADED:
        return _LOADED[code]
    path = os.path.join(LANG_DIR, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            full = json.load(fh)
        d = full["caption"]
        messages = d["messages"]
        if not (isinstance(messages, dict) and all(isinstance(v, str) for v in messages.values())):
            raise TypeError(messages)
        loaded = {
            "MESSAGES": messages,
            "ASKS": [(re.compile(x["regex"]), x["name"], x["id"]) for x in d["asks"]],
            "FILLER_TAGS": {t.lower() for t in d["filler_tags"]},
            "CONCRETE": build_concrete(full["concrete"]),
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


def visible_window(text, cut):
    """What the feed shows. Instagram cuts mid-word, so this does too."""
    flat = text.strip()
    return flat if len(flat) <= cut else flat[:cut]


def render_box(window, truncated, out=sys.stdout, lang="en"):
    M = load_lang(lang)["MESSAGES"]
    width = FEED_WIDTH
    print(say(M, "feed_title"), file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(textwrap.wrap(raw, width) or [""])
    for line in lines[:8]:
        print(f"  | {line:<{width}} |", file=out)
    print(say(M, "feed_more") if truncated else say(M, "feed_whole"), file=out)


def analyse(text, cut=TRUNCATE, keywords=None, lang="en"):
    # Decomposed accents (NFD, macOS paste) split words in `re` and count twice
    # as characters: compose them, the way a reader sees the caption.
    L = load_lang(lang)
    M = L["MESSAGES"]
    text = unicodedata.normalize("NFC", text).rstrip()
    stripped = text.strip()
    chars = len(stripped)
    lines = [l for l in stripped.split("\n")]
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(stripped)
    window = visible_window(stripped, cut)
    truncated = chars > cut
    match = stripped.translate(APOSTROPHES)
    fired = [(name, ask_id) for pattern, name, ask_id in L["ASKS"] if pattern.search(match)]
    asks = [name for name, _ in fired]
    filler = [t for t in tags if t.lower() in L["FILLER_TAGS"]]
    keywords = [unicodedata.normalize("NFC", k.strip()) for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    if chars > LIMIT:
        add("LENGTH", "FAIL", say(M, "length_over", chars=chars, limit=LIMIT, over=chars - LIMIT))
    else:
        add("LENGTH", "PASS", say(M, "length_ok", chars=chars, limit=LIMIT))

    if not first_line:
        add("FIRST LINE", "FAIL", say(M, "first_line_blank"))
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL", say(M, "first_line_tag"))
    elif len(first_line) > cut:
        add("FIRST LINE", "WARN", say(M, "first_line_cut", chars=len(first_line), cut=cut))
    else:
        add("FIRST LINE", "PASS", say(M, "first_line_whole", chars=len(first_line)))

    concrete = len(concrete_marks(window, L["CONCRETE"]))
    if concrete:
        add("HOOK IS CONCRETE", "PASS", say(M, "hook_concrete", count=concrete))
    else:
        add("HOOK IS CONCRETE", "WARN", say(M, "hook_abstract", count=concrete))

    if len(tags) > HASHTAG_LIMIT:
        add("HASHTAGS", "FAIL", say(M, "hashtags_over", count=len(tags), limit=HASHTAG_LIMIT))
    elif len(tags) == HASHTAG_LIMIT and filler:
        add("HASHTAGS", "WARN", say(M, "hashtags_cap_generic", count=len(tags),
                                    generic=len(filler)))
    elif filler:
        add("HASHTAGS", "WARN", say(M, "hashtags_generic", count=len(tags),
                                    generic=len(filler), examples=", ".join(filler[:3])))
    elif tags:
        add("HASHTAGS", "PASS", say(M, "hashtags_listed", count=len(tags), tags=" ".join(tags)))
    else:
        add("HASHTAGS", "PASS", say(M, "hashtags_none", count=len(tags)))

    if not tags:
        add("TAG PLACEMENT", "PASS", say(M, "placement_none"))
    elif any(re.search(r"(?:^|\s)" + re.escape(t) + r"\b", window) for t in tags):
        add("TAG PLACEMENT", "WARN", say(M, "placement_window"))
    else:
        add("TAG PLACEMENT", "PASS", say(M, "placement_below"))

    if links:
        add("LINKS", "WARN", say(M, "links_found", count=len(links)))
    else:
        add("LINKS", "PASS", say(M, "links_none"))

    if len(asks) == 1:
        add("ONE ASK", "PASS", say(M, "ask_one", ask=asks[0]))
    elif not asks:
        add("ONE ASK", "WARN", say(M, "ask_none"))
    else:
        add("ONE ASK", "WARN", say(M, "ask_many", count=len(asks), asks=", ".join(asks)))

    density = len(emoji) * 100 / max(chars, 1)
    if density > 4:
        add("EMOJI", "WARN", say(M, "emoji_decoration", count=len(emoji), density=density))
    else:
        add("EMOJI", "PASS", say(M, "emoji_plain", count=len(emoji), density=density))

    if keywords:
        low = match.lower()
        win = window.translate(APOSTROPHES).lower()
        key = lambda k: k.translate(APOSTROPHES).lower()   # noqa: E731
        found = [k for k in keywords if key(k) in low]
        missing = [k for k in keywords if key(k) not in low]
        in_window = [k for k in found if key(k) in win]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("SEARCH TERMS", status,
            say(M, "terms_present", found=len(found), total=len(keywords))
            + (say(M, "terms_in_window", count=len(in_window)) if found else "")
            + (say(M, "terms_missing", missing=", ".join(missing)) if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")

    return {
        "characters": chars, "limit": LIMIT, "truncate_at": cut,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks, "ask_ids": [i for _, i in fired],
        "checks": checks, "verdict": verdict,
    }


def render(a, out=sys.stdout, lang="en"):
    M = load_lang(lang)["MESSAGES"]
    head = say(M, "head", chars=a["characters"], limit=a["limit"],
               tags=len(a["hashtags"]), asks=len(a["asks"]))
    print("\n" + head, file=out)
    print("=" * max(len(head), 62), file=out)
    render_box(a["visible"], a["truncated"], out=out, lang=lang)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<17} {c['detail']}", file=out)
    print("-" * max(len(head), 62), file=out)
    print(say(M, "verdict_line", verdict=a["verdict"]), file=out)


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
    ap = argparse.ArgumentParser(description="Lint an Instagram caption.")
    ap.add_argument("input", nargs="?", default="-", help="caption file, or - for stdin")
    ap.add_argument("--truncate", type=int, default=TRUNCATE,
                    help=f"characters shown before '... more' (default {TRUNCATE})")
    ap.add_argument("--keywords", default="", help="comma-separated terms you want to be found for")
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
        a = analyse(raw, cut=args.truncate, keywords=args.keywords.split(","), lang=lang)
    except LangError as err:
        print(f"caption.py: cannot load language data, {err}", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        render(a, lang=lang)
    sys.exit(0 if a["verdict"] == "READY" else 1)


if __name__ == "__main__":
    main()
