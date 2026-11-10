---
name: ig-story
description: >-
  Use when the user says "stories", "what do I post on my story", "story
  sequence", "poll idea", "I have nothing to story about", or wants to sell
  something without making a post about it. Use quando o usuário diz
  "stories", "o que eu posto no story", "sequência de stories", "ideia de
  enquete", "não tenho nada pra postar no story", ou quer vender algo sem
  fazer um post sobre isso.
---

# ig-story

Stories are not a smaller feed. The feed is how strangers find you. Stories are
how the people who already follow you decide whether you are a person worth
buying from, and they are the only surface on Instagram where a tap turns into
a conversation in one move.

Nobody outside your followers sees these, so the job is completely different:
depth, not reach.

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

## The daily shape

Three to seven frames a day. Beyond about seven, the tap-forward rate climbs
and the last frames play to nobody, which is exactly where people put the ask.

```
1       THE OPEN     something happening today, with a face or a hand in it.
2-3     THE MIDDLE   the actual content: the process, the result, the mistake.
4       THE ASK      one sticker. Poll, question box, quiz or link.
5       THE CLOSE    the answer, the outcome, or tomorrow's setup.
```

Put the ask at frame 4, not frame 7. Completion drops with every tap and the
ask should be seen by the people who are still there.

## The stickers, and what each is actually for

| sticker | job | use when |
| --- | --- | --- |
| **Poll** | the cheapest tap there is | you want volume of response, not information |
| **Question box** | harvesting the exact words people use | you need content ideas or objections, verbatim |
| **Quiz** | teaching by letting them be wrong | there is a common misconception in the niche |
| **Slider** | vibe check | nothing important. Fun, low value |
| **Link** | the only clickable surface besides the bio | there is somewhere real to go |
| **Countdown** | a deadline people can subscribe to | a launch, a live, a close date |
| **Add yours** | reach beyond your followers, occasionally | the prompt is one anyone in the niche can answer |

The question box is the most undervalued one in the list. Every answer is a
caption, a Reel hook or a DM opener written in the audience's own words. Feed
them to `/ig-reel` as formula #16.

## Rules

- **A face or a hand in the first frame.** Text on a coloured background gets
  tapped through, and the first frame decides whether the rest get watched.
- **One idea per frame.** Reading a paragraph on a story is not a thing anyone
  does.
- **Keep text inside the middle.** On 1080x1920, nothing above y=250 or below
  y=1600. The profile row sits on top and the reply bar sits underneath.
- **Talk to one person.** "You" singular. Stories are the closest thing to a
  DM that is not one.
- **Do not repost your own feed post to stories with no comment.** It is the
  single most ignored frame on the platform. If you are pointing at a post, say
  what happened in the comments and why it is worth going back for.
- **Sell on stories, not in posts.** Three frames of context, one frame of
  offer, one frame of proof. That sequence sells more than a feed post about
  the same thing and costs you no reach.

## The DM funnel, done honestly

The sequence that works: a story that names a problem, a question box or a poll
that lets people say "that's me", and then a reply to each person who answered.
The conversation starts because they spoke first.

Automated keyword DM replies are a real, supported feature for professional
accounts, through Instagram's own tools and approved partners. Bulk DMing
people who did not interact is not, and it is what gets accounts restricted.
The rule is simple: **they act first, then you reply.**

## Output

The frames in order, each with what is on screen, what is said, and which
sticker, plus what to do with the answers:

```
STORIES  ·  Tuesday  ·  5 frames

1  [selfie, walking]      "Third refund request this year. Same reason."
2  [screen recording]     the clause, highlighted
3  [talking]              "Approval is a feeling. Delivery is a date."
4  [poll]                 "Have you been burned by a late approval?"  Yes / Not yet
5  [text on photo]        "Reply and I will send you the clause."

After: everyone who votes Yes gets a reply. That is the whole funnel.
```

Nothing is posted until the user says yes to the sequence. The user posts it.
When they approve the sequence, append
one line to `~/.claude/instagram/log.md` (create it if it is missing), type
`story`, with frame 1's line as `first line` and `-` as `formula`, so
`/ig-plan` does not repeat the day's theme:

<!-- shared:log-schema -->
One line per item, oldest at the top, newest at the bottom:

```text
- YYYY-MM-DD | type | formula | first line | account
```

- `type`: `reel`, `carousel`, `story` or `comment`.
- `formula`: the hook formula as `#n` from `ig-reel/hooks.json`, or `-` when
  none was used.
- `first line`: the hook or opening line as the user approved it, with any `|`
  written as `/`.
- `account`: the handle it went out on; for a comment, the account commented
  on.

Read a line by splitting on ` | `. Lines that do not have this shape are older
notes: keep them, do not rewrite them.
<!-- /shared:log-schema -->
