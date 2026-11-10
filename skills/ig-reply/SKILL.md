---
name: ig-reply
description: >-
  Use when the user pastes the comments under their own reels or posts, says
  "reply to these", "handle my comments", "someone said X on my reel", or is
  dealing with a critic, a hater or a lead in their comments. Use quando o
  usuário cola os comentários dos próprios reels ou posts, diz "responde
  esses", "cuida dos meus comentários", "fulano comentou X no meu reel", ou
  está lidando com um crítico, um hater ou um lead nos comentários.
---

# ig-reply

The comment thread under your own post is where reach is decided. Every reply
is another interaction on the post, replies arriving in the first hour do most
of the work, and on Instagram a reply can also be a Reel, which is the single
most underused move on the platform.

But the value is not equal across comments, so this skill sorts before it
writes.

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

## Input

The user pastes the comments, ideally with handles. Screenshots are fine. Do
not scrape the thread with a browser tool.

## Triage first

Sort every comment into one of six buckets and say the counts out loud:

| bucket | what it is | what it gets |
| --- | --- | --- |
| **KEYWORD** | the word you asked them to comment | the promised thing, sent by hand or by your approved tool |
| **LEAD** | someone describing the problem you solve | a real answer in public, then a door |
| **SUBSTANCE** | adds data, disagrees, extends | the longest reply on the thread |
| **QUESTION** | a question a lot of people have | this one becomes a Reel, not just a reply |
| **SUPPORT** | "🔥", "great post", a tag | a like, and 3 to 8 words at most |
| **NOISE** | pitch, spam, bad faith, bait | nothing, or one line and out |

Write in that order and stop when the value stops.

## The move most people miss

If a question in the comments is one that thirty other people also have,
**reply to it with a Reel**. Instagram will attach the comment to the new video
as a sticker, the person who asked gets notified, and a question with real
demand behind it becomes a post with the hook already written for you. Flag
every QUESTION that qualifies and hand it to `/ig-reel` as formula #16.

## How to reply

- **Answer the actual question.** If someone asks how, tell them how, in the
  reply. Do not send them to the DMs to hear an answer they could have had.
- **Use their name once**, at the start, without an exclamation mark.
- **Match their length.** A four-word comment does not get a four-line reply.
- **To a critic:** concede the true part first, in their words, then hold the
  line. Never delete, never get defensive, never reply twice on the same
  thread.
- **To a hater:** nothing. A reply is reach, and reach is what they came for.
  Hide the comment if it is abusive. Instagram's comment controls exist and
  using them is not losing.
- **To a lead:** answer fully in public. The door is one sentence at the end
  and it is an offer of help, not a pitch. The public answer is what makes the
  next person DM you.

## Keyword comments

If the post used a keyword ask, those comments are the whole point of the post.
Every one of them is a person who raised their hand. Reply to each, then send
what was promised. If the user has automation set up through Instagram's own
tools or an approved partner, say so and let it run; if not, the replies are
manual and that is fine at this volume. Never bulk-DM people who did not
comment.

## Output

One block, grouped by bucket, each reply copy-ready and already humanized:

```
REPLIES  ·  84 comments  ·  41 KEYWORD, 2 LEAD, 3 SUBSTANCE, 2 QUESTION, 34 SUPPORT, 2 NOISE

KEYWORD  (41)  send the clause. One line each, same warmth, not copy-paste.

LEAD
@handle - "we had this exact thing happen in June"
> The bit that fixed it for us was moving the payment trigger off approval
> entirely. Happy to send the wording if it is useful.

QUESTION -> REEL
@handle - "what do you do if they refuse to sign it?"
  34 likes on this comment. That is a Reel, not a reply. Formula #16.

NOISE  (2)  skipped. Replying gives them reach.
```

Then the gate: nothing is posted until the user says yes. They paste the
replies.
