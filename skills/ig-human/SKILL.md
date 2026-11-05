---
name: ig-human
description: >-
  Use when a draft has to sound like a person before it is shown or
  posted, when the user says "humanize this", "does this sound like AI",
  "remove the em dashes", "de-slop this", "this sounds like ChatGPT", and
  before any caption, script, comment, reply or DM goes to the user. Use
  quando um texto precisa soar como gente antes de ser mostrado ou postado,
  quando o usuário diz "humaniza isso", "isso parece IA?", "tira os
  travessões", "isso tá com cara de ChatGPT", e antes de qualquer legenda,
  roteiro, comentário, resposta ou DM chegar ao usuário.
---

# ig-human

Two tools live in this folder and they both actually run. Use them. Do not
eyeball this.

```bash
python3 {skill_dir}/humanize.py draft.txt --report --lang {language}   # clean it, show what changed
python3 {skill_dir}/detect.py draft.txt --lang {language}              # score it, five checks
python3 {skill_dir}/detect.py before.txt after.txt --lang {language}   # prove the delta
```

`--lexicon` wins over `--lang` when both are given.

Both read `slop.en.json`: 240 stock words and phrases with plain-English
replacements, 18 invisible character classes, 11 typographic substitutions and
16 structural tells. The last block of each list is Instagram-specific, the
vocabulary that only shows up in captions and voiceovers. It is meant to be
edited. If the user has a word they always use that the lexicon strips, take it
out of the file.

<!-- shared:before-you-write -->
## Before you write

The same steps open every ig-* skill.

1. Read `~/.claude/instagram/voice.md` if it exists: who the user is, who they
   talk to, how they sound, what they never say. If it does not exist, ask once
   for three of their own posts (reels, captions or comments), infer the voice
   from them, write the file, and tell the user you did. Never invent a voice.
2. Answer in the language of its **Language:** line: `en` is English, `pt-BR`
   is Brazilian Portuguese. With `auto`, no voice.md or no Language line, answer
   in the language the user writes to you in. These instructions are in English;
   what you write for the user is in their language.
3. `{language}` in a command is that same line: `en`, `pt-BR` or `auto`. With no
   voice.md, or no Language line in it, use `en`. A language whose data is not
   in the skill folder yet is refused with exit 2 and the name of the missing
   file. Tell the user, and run with `--lang en` only if they agree, saying the
   checks are tuned for English.
4. `{skill_dir}` is the folder this SKILL.md was loaded from (Claude Code names
   it as the skill's base directory). Run every script as
   `python3 {skill_dir}/name.py`, never from the current folder, and read every
   file this skill calls "in this folder" from there. If the folder has no
   scripts (this file was pasted on its own), do the checks by hand and say
   they were not run.
<!-- /shared:before-you-write -->

## Why this matters more on Instagram than it looks

Captions are short and scripts get said out loud. A written-sounding line in a
600-character caption is a larger share of the text than the same line in an
essay, and a voiceover that nobody could say naturally is obvious in the first
take. The tell here is not a detector flagging the post. The tell is a person
scrolling past something that reads like a brand, or a creator stumbling over
their own script.

## What gets fixed automatically

**1. Invisible characters.** Zero-width spaces and joiners, word joiners, soft
hyphens, byte-order marks, Unicode tag characters, invisible separators,
non-breaking and narrow spaces. A keyboard does not produce these. They survive
copy-paste, they are invisible in every editor, and they are the most
mechanical thing in generated text. `humanize.py` deletes every one, including
any remaining Unicode format character it does not have a name for.

**2. Typography.** Em dash to comma, en dash to hyphen, curly quotes to
straight, ellipsis to three dots, bullet character to hyphen. The em dash pass
is the one that matters: it collapses the dash to a comma and then cleans up
the double punctuation and orphaned periods that leaves behind.

**3. The slop lexicon.** delve, leverage, robust, seamless, crucial, testament
to, "in today's fast-paced world", plus the Instagram block: "stop scrolling",
"in today's video", "follow for more", "tag someone who needs this", "the
algorithm loves", "run don't walk". Each swapped for a plain word or deleted,
with capitalisation preserved and URLs left untouched. A deletion that would
leave a clause hanging is not made: "Follow for more if you love design."
would come out as "If you love design.", so the sentence stays as written and
comes back flagged for a rewrite (a "that" after a deleted opener goes with it:
"I'm thrilled to share that we hit 10k" becomes "We hit 10k"). What no pass
changed comes back as written: the writer's line breaks, blank lines, double
spaces and lower case after a "..." stay.

## What does NOT get fixed automatically

Structural tells get **flagged, not rewritten**, because changing the shape of
a sentence needs judgement:

- "It's not just X, it's Y" and "not only X but also Y"
- Rule-of-three triads
- Rhetorical one-word question lines: "The result?"
- The video preamble: "in this video I'm going to show you"
- Emoji bullet lists
- Three or more shouted words in a row
- Hashtag walls
- Reflex bait: "follow for more", "tag someone who", "double tap if"
- A stock phrase with a clause hanging on it ("double tap if you agree",
  "let me know in the comments what you think"): deleting the phrase would
  leave a fragment, so it is kept and flagged

That list is your job. Rewrite each flagged line by hand, keeping the meaning,
then re-run `detect.py`. This is the part that moves the score from REVIEW to
PASS, and it is the part a script cannot do.

## The five checks

`detect.py` scores five signals 0-100, higher is more human:

| check | what it measures | machine looks like |
| --- | --- | --- |
| BURSTINESS | sentence-length variation | every sentence the same length |
| SPECIFICITY | numbers, names, concrete markers per 100 words | abstract nouns, no figures |
| SLOP DENSITY | lexicon hits per 100 words | stock vocabulary |
| FINGERPRINT | invisible chars, em dashes, curly quotes per 1k chars | typographically perfect |
| VOICE | contractions, person, structural tells | no contractions, staged reveals |

The verdict weights the mean at 60% and the **weakest single check** at 40%,
because one signal is enough. PASS needs an overall of 70+ with no check
below 55, and no structural tell left: while one remains the verdict stops at
REVIEW, whatever the score, and the output says how many. In pt-BR the
lexicon is not calibrated yet (`"calibrated": false`), so `detect.py` stays at
REVIEW and says why; read the text by hand and do not declare PASS.

## Say this honestly

These are five local heuristics modelled on the signals public detectors key
on. They run entirely on the user's machine and nothing is uploaded. They are
**not** GPTZero, Originality, Copyleaks, Winston or Turnitin, they do not call
those APIs, and they cannot promise those verdicts. Fixing what they measure
does tend to move those numbers, because they are measuring the same underlying
things. That is the claim. Do not make a bigger one on the user's behalf, and
do not tell a user their text is undetectable.

## Order of operations

1. `python3 {skill_dir}/humanize.py draft.txt -o clean.txt --report --lang {language}`
2. Read the structural flags, held deletions included. Rewrite those lines yourself.
3. `python3 {skill_dir}/detect.py draft.txt clean.txt --lang {language}` to show the before and after.
4. If the verdict is not PASS, fix what the output names (the structural tells
   still left, or else the weakest check) and go again. Two rounds is normal.
   Five means the draft was written by formula, and the fix is a different
   draft, not more passes.
5. Show the user the cleaned text and the score. Never the score alone.
