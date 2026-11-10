---
name: ig-dm
description: >-
  Use when the user is reaching out to someone specific in Instagram DMs, says
  "DM this person", "what do I send them", "outreach message", "how do I
  follow up", "pitch this brand", or needs the message that delivers a comment
  keyword. Use quando o usuário vai abordar alguém específico na DM do
  Instagram, diz "manda DM pra essa pessoa", "o que eu mando pra ela",
  "mensagem de prospecção", "como faço o follow-up", "faz o pitch pra essa
  marca", ou precisa da mensagem que entrega a palavra-chave de um comentário.
---

# ig-dm

Instagram DMs are the only place on the platform where money actually changes
hands, and they are also where most accounts burn the goodwill their content
earned. The difference is entirely about who moved first.

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

## The three kinds of DM, and only three are worth writing

**1. The reply to a hand raised.** They commented the keyword, answered the
poll, replied to a story, or saved and asked. They moved first. This is 90% of
the DMs worth sending and it converts because it is not outreach.

**2. The warm approach.** Someone whose posts the user has genuinely been
commenting on for weeks. There is a shared thread of conversation already.

**3. The collab or brand pitch.** A specific proposal to a specific account,
with a reason it is them.

Everything else is cold DMing strangers, which is what everybody else does, and
it is why reply rates sit where they do. If the user is asking for a cold
sequence, say plainly that it is the lowest-yield thing they could do with the
same hour, and offer the alternative: comment on those ten accounts for two
weeks first. Then write it if they still want it.

## Before writing, get the specifics

Ask in one batched question:

1. **Who** - handle, what they do, and what they posted or did that started
   this.
2. **The trigger** - the actual reason to message today. A keyword they
   commented, a story they replied to, a post they published. Not "they fit the
   ICP".
3. **What the user wants** - a conversation, a sale, a collab, a referral. Be
   honest internally, even if the message does not lead with it.

If there is no trigger, there is no message. Say so.

## The keyword delivery

The most common DM in this pack and the easiest to ruin. They commented one
word. They are expecting the thing. So:

```
{their name}, here it is: {the thing, or the link}.

{one line on how to use it}

{one question they can answer in four words}
```

Send the thing **first**, in message one, with no gate. A keyword post that
delivers a "before I send it, can I ask what you do?" is a bait and switch and
it is remembered. The question at the end is what starts the conversation, and
it is optional for them.

Automated keyword replies are a supported feature for professional accounts,
through Instagram's own tools or an approved partner. Using that is fine.
Sending unsolicited bulk DMs is not, and it is the fastest route to a
restricted account.

## The first message to someone warm

- **Two to four sentences.** A screen of text is a delete.
- **Reference the specific thing.** The comment, the post, the reply. In their
  words.
- **Give before asking.** A number, a template, a name, an answer.
- **One ask, small.** "Worth a quick call?" beats "let me walk you through the
  platform".
- **No link and no calendar in message one.** It reads as a funnel because it
  is one.
- **No voice note to a stranger.** It is a great tool and it is for people who
  already know the user's voice.

## The collab pitch

Four lines, in this order: what you have watched them do, the specific idea,
what they get, what you need from them. A collab post lands on both grids and
reaches both audiences, which is the strongest single growth mechanic on
Instagram that does not involve paying anybody. Pitch it as that and be
concrete about who does what.

## Follow-ups

Two. That is the number.

- **+4 days** - add something new. Never "just bumping this". If there is
  nothing new, there is no follow-up.
- **+10 days** - the close-the-loop message. Say you will stop, and mean it.
  This one gets a surprising share of the total replies, because it removes the
  pressure.

Then stop. A third converts nobody and costs the relationship.

## Never

- Never automate outreach DMs, and never use a tool that sends on a schedule to
  people who did not interact. It violates Instagram's Terms of Use and
  restricts the account.
- Never fabricate having watched something, a mutual, or a shared anything.
- Never open with "Hey! Quick question" and then not ask a question.
- Never send the pitch in the same message as the compliment.

## Output

The message, the character count, and the two follow-ups with the day each
goes out, all run through `/ig-human`. Nothing is sent until the user says
yes to it. The user sends every one of them by hand, or through their own
approved automation for keyword replies only.
