# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Claude Code plugin (`.claude-plugin/plugin.json` + `marketplace.json`) that ships 13 skills under `skills/ig-*/`. Each skill is a `SKILL.md` (frontmatter `name` + `description`, the description is the trigger text). Four of them (`ig-reel`, `ig-caption`, `ig-human`, `ig-viral`) ship Python CLI tools, six scripts in all; `ig-profile` ships only JSON data. There is no build, no package manager, no dependencies, no linter config. Tools are stdlib-only Python 3 and must stay that way (the README promises "no dependencies, no network").

Users install by copying `skills/ig-*` into `~/.claude/skills/`, or by pasting a single `SKILL.md` into a chat. So **every skill folder must work on its own**, and a SKILL.md must still make sense without its scripts.

## Running the tools

Every tool reads a file path or `-` / stdin, and supports `--json`. Run from anywhere; data files are resolved relative to the script (`HERE = os.path.dirname(__file__)`).

```bash
python3 skills/ig-reel/hookscore.py hooks.txt          # one hook per line; or --hook "..."
python3 skills/ig-reel/beats.py script.txt --target 30 [--wpm 165]
python3 skills/ig-caption/caption.py caption.txt --keywords "a,b" [--truncate 125]
python3 skills/ig-human/humanize.py draft.txt --report [-o out.txt] [--lexicon slop.json]
python3 skills/ig-human/detect.py draft.txt [after.txt]  # second arg = before/after delta
python3 skills/ig-viral/swipe.py captured.tsv [--out swipe.md] [--hooks path/to/hooks.json]
```

Exit codes are meaningful (skills use them as verdicts): `hookscore` exits 1 if the best hook scores < 70; `caption` exits 1 unless verdict is `READY`; `detect` exits 1 unless the last result is `PASS`; `2` means bad input. The exit code is the same with `--json`. `humanize --report` writes the report to stderr and the cleaned text to stdout.

## Tests

```bash
python3 -m unittest discover tests          # whole suite, stdlib unittest
python3 -m unittest discover tests -p "test_caption.py"   # one file
```

Run from the repo root. Golden tests pin the numbers in the README example blocks, and `test_invariants.ReadmeBlocksAreRealOutput` checks those README lines verbatim against real tool output on the inputs in `tests/fixtures/`. So when a tool's output changes, update the README block and the pinned values together. Invariant tests also derive the prose counts from the JSONs, check that duplicated regexes have not drifted, that each tool folder runs from a lone copy, and that every import is stdlib. A test marked `expectedFailure` is a known bug logged for a later phase, not a broken test.

## Architecture and coupling

- **Data vs. logic.** Tunable content lives in JSON, meant to be edited by users: `ig-human/slop.json` (lexicon + replacements, invisible-char classes, typography substitutions, structural tells), `ig-reel/hooks.json` (26 formulas, each with a `match` regex), `ig-profile/rubric.json` (12-item, 100-point score, read by the model, not by code). Prefer changing the JSON over hardcoding in Python.
- **`humanize.py` fixes, `detect.py` scores.** Both read `slop.json`. humanize applies three passes (invisible chars → typography → lexicon) and only *flags* structural tells (they need human rewriting, not regex). Lowercase-only voices are deliberately preserved when restoring capitals after a deleted opener.
- **Cross-skill dependency:** `ig-viral/swipe.py` reads `../ig-reel/hooks.json` and optionally imports `hookscore.run` from `../ig-reel` via `sys.path`. Both are wrapped so swipe degrades gracefully if `ig-viral` is copied alone — keep it that way. Changing `hookscore.run`'s signature or `hooks.json`'s schema affects swipe.
- **Duplicated regexes.** `WORD_RE`, `CONCRETE_RE`, `EMOJI_RE`, etc. are copied across scripts on purpose (each folder is standalone). When fixing one (e.g. the spoken-numbers fix in SPECIFICITY), check the sibling copies in the other scripts.
- **Shared user state** lives outside the repo in `~/.claude/instagram/`: `voice.md` (from `templates/voice.md`, read by every skill), `swipe.md` (written by `/ig-viral`, read by `/ig-reel` and `/ig-plan`), `log.md` (appended on post approval, read by `/ig-plan`, `/ig-comment`, `/ig-audit`), `plan.md` (written by `/ig-plan`).

## Product invariants (stated in the README; don't violate them in skills or code)

- Nothing posts to Instagram. Every skill ends with a copy-ready block and an explicit user approval. No browser automation, scraping, login, or third-party posting tools.
- Never fabricate metrics, clients or outcomes; a missing number becomes `{{your number}}` plus a flag.
- The detection checks are local heuristics; never claim they are GPTZero/Originality/etc. or "undetectable".
- Platform constants go stale (e.g. `HASHTAG_LIMIT = 5` in `caption.py`, changed 18 Dec 2025). When changing one, update the comment's date and the README/SKILL.md mentions too.
- Counts are quoted in prose ("154 terms", "26 formulas", "13 skills", "18 invisible classes"). Adding to the JSON means updating those numbers in `README.md`, the SKILL.md files and `plugin.json`'s description.
