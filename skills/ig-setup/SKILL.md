---
name: ig-setup
description: >-
  Use when the user says "set me up", "get started with the Instagram skills",
  "write my voice.md", "write my voice.md from these", "update my voice.md", or
  pastes their own reels or captions and asks the pack to learn how they sound.
  Use quando o usuário diz "me configura", "começar com as skills de
  Instagram", "escreve meu voice.md", "escreve meu voice.md a partir destes",
  "atualiza meu voice.md", ou cola reels ou legendas suas e pede para o pacote
  aprender como ele fala.
---

# ig-setup

Every other skill in the pack is only as good as one file: `voice.md`. Without
it they write in a voice nobody owns. This skill writes that file with the
user, picks the language their posts are checked in, and says which skill to
run next. It takes ten minutes and it happens once.

<!-- shared:before-you-write -->
## Before you write

The same steps open every ig-* skill.

1. Read `~/.claude/instagram/voice.md` if it exists: who the user is, who they
   talk to, how they sound, what they never say. If it does not exist, ask once
   for three of their own posts (reels, captions or comments) and the language
   they post in (`en`, `pt-BR`, or `auto` for both). Infer the voice from the
   posts, put the language on a line of its own, written exactly
   `- **Language:** pt-BR` (with their code), show the user the file, and write
   `~/.claude/instagram/voice.md` only after they say yes. Never invent a voice.
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
5. **Never fabricate.** A number, client, result or quote under the user's
   name comes from what they told you or from the **Proof I can use** section
   of voice.md (**Provas que posso usar** in the pt-BR form), never from you,
   not even as an example. When one is needed and missing, write
   `{{your number}}` in its place and tell the user what to fill.
<!-- /shared:before-you-write -->

Writing voice.md is the whole job here, so step 1 above becomes the steps
below. Follow them instead of writing the file straight from three posts.

## 1. What is already there

Look in `~/.claude/instagram/`.

- **No voice.md:** start at step 2.
- **A voice.md:** show which fields are filled and which are empty, and ask
  what changed. Edit only those fields. Never rewrite a file the user already
  filled in, and never drop a field they wrote.

The pack reads one voice.md, for one account. If the user posts for more than
one (an agency, clients, a second brand), say so plainly, ask which account
this one is for, and write it for that account.

## 2. The language

Ask which language they post in, not which language they are writing to you
in. Most people answer the second by accident.

- `en` or `pt-BR`: the word lists and the checks of every script match it.
  Recommend this.
- `auto`: the scripts guess from each text and say what they picked. A
  six-word hook can tie, and a tie falls to `en`. Only for someone who really
  posts in both.

This goes on the **Language:** line, written exactly like this, a list item
with the label in bold and the code after it:

```
- **Language:** pt-BR
```

The label stays in English in both forms, because it is the line every skill
looks for. A heading, a translated label or a different shape is a voice.md
the other skills read as having no language, and they fall back to `en`.

## 3. The form

Use `voice.en.md` in this folder for `en`, `voice.pt-BR.md` for `pt-BR`. For
`auto`, the one in the language the user writes to you in. Keep its headings
and its `- **label:**` lines as they are, and write the answers after them.
If you cannot read either file (this SKILL.md was pasted on its own, or the
read was refused), say so, and build the file from the six sections named
below, with `- **Language:** {code}` as its first line under the first one.

Two ways to fill it. Offer both and let the user pick.

**From their posts (better).** Ask for three of their own reels (the spoken
script, or the on-screen text), captions or comments, the three that sound
most like them. They paste the text. Do not log into Instagram, do not open
their profile, do not fetch anything. From the three, fill **What I sound
like**: how they open, sentence length, words that recur, emoji, swearing,
whether they talk to the camera. Then ask for what posts cannot show: who
they talk to, what they sell, their positions, what is off limits, their
proof, their ask.

**By interview.** One section at a time, in the order of the form: who I am,
what I sound like, my positions, off limits, proof I can use, the ask. Short
questions, the user's own words in the answers. Never more than one section
per message.

Rules for both:

- A field the user did not answer stays empty. Do not guess a niche from a
  bio, a tone from one caption, or a pace nobody timed.
- **Proof I can use** holds only numbers, outcomes and stories the user gave
  you, that they would put their name on, copied in their words: a paraphrase
  of a proof is a new claim. Who they sell to is not proof. Never round up,
  never add one. If it stays empty, every draft from the other skills comes
  back with `{{your number}}`, which is the point.
- **Pace** is words per minute only if they timed themselves reading a
  script. Otherwise leave it empty: `beats.py` has a default.
- Mark what you inferred from their posts with `(from your posts)` so they
  can see what to correct.

## 4. Show it, then write it

Show the whole file as one copy-ready block: the form from its first `##`
heading down (leave out the instructions above it), with their answers in.
Ask: "Anything wrong or missing before I save this?"

Write `~/.claude/instagram/voice.md` only after a yes. Create the folder if it
is not there. If a voice.md was already there, show what changes first, field
by field, and save over it only after that yes. Then say where the file is
and that every skill reads it from now on.

## 5. What to run next

Three lines, no more, in their language:

- `/ig-viral` first, if they do not know what is working in their niche yet:
  it writes the swipe file the others read.
- Then the loop for each post: `/ig-reel` (hook and script), `/ig-caption`,
  and `/ig-human` on anything before it ships.
- `/ig-profile` once, `/ig-plan` once a week.

Nothing here posts to Instagram, and no skill in the pack ever does. The user
copies what they approve.
