---
name: ig-audit
description: >-
  Use when the user pastes their Instagram insights, analytics or past posts
  and asks "what's working", "why did this flop", "read my analytics", "audit
  my content", or wants to know which reels to make more of and which to stop.
  Use quando o usuário cola os insights, as métricas ou os posts antigos do
  Instagram e pergunta "o que está funcionando", "por que esse flopou", "lê
  minhas métricas", "audita meu conteúdo", ou quer saber o que fazer mais e o
  que parar de postar.
---

# ig-audit

The only honest source of what works for an account is that account. Every
rule in every Instagram guide, including the ones in this pack, is a prior.
The user's own last 30 posts are the evidence.

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

## Input

Ask for whichever the user has:

- Insights per post: views, reach, interactions, watch time, saves, shares,
  follows, and the non-follower share of reach. Screenshots are fine.
- Or the retention graph for their best and worst recent reels. This one
  screenshot is worth more than the rest combined.
- Or just the posts and their view counts, which is enough for a first pass.

Also read `~/.claude/instagram/log.md` if it exists, since it records which
hook formula each post used. Match a post to its line by date and first line.

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

## What to actually measure

Raw views is the least useful number on the page, because it is mostly a
function of how many people already follow the account. Compute these instead
and show the working:

| metric | how | what it tells you |
| --- | --- | --- |
| **Outlier multiple** | views / the account's own median views | whether this was a real hit or a normal day |
| **Non-follower reach** | % of reach from people who do not follow | whether it travelled at all |
| **Hold at 3s** | viewers still there at 3s / viewers who started | whether the hook worked. This is the hook's grade. |
| **Average watch time** | straight from insights | whether the middle worked |
| **Sends per reach** | shares / reach | the strongest single signal you can earn. A send is a person putting their name on it. |
| **Follows per reach** | follows / reach | whether the profile converted the attention |

Rank by outlier multiple and sends per reach, not views. A reel with 4,000
views and 90 sends beat the one with 60,000 views and 11.

## Then find the pattern

With the top five and bottom five side by side, look for what separates them,
and be willing to conclude something the user will not like:

- **Hold at 3 seconds.** If the top and bottom differ here, it is the hook and
  nothing else, and everything downstream is a distraction.
- **Hook formula.** Which ids from `ig-reel/hooks.json` are in the top five?
- **Format.** Reel, carousel, single image.
- **Length.** Group into under 15s, 15 to 30s, 30 to 60s, over 60s.
- **Theme.**
- **Whether the user replied to comments in the first hour.**
- **Day and time.** Check this **last** and only if the others show nothing.
  It is almost never the cause and it is where people want it to be.

State the finding as a claim with the evidence attached, and say how confident
it is. With 30 posts you can see a pattern. With 6 you cannot, and saying so is
better than inventing one.

## The distinction that saves people months

**A reel that gets views and no follows is not a failed reel, it is a profile
problem.** A reel that gets no views is a hook problem. Separate the two before
recommending anything. If non-follower reach is high and follows per reach is
low, stop rewriting hooks and go to `/ig-profile`.

## Output

```
AUDIT  ·  31 posts  ·  Jun 12 - Sep 5  ·  median views 4,100

TOP 5 BY OUTLIER MULTIPLE
  18.2x  #3  Nobody Tells You   74,600 views  62% non-follower  hold@3s 71%  128 sends
   6.4x  #1  Cost Confession    26,300 views  48% non-follower  hold@3s 64%   71 sends
  ...

BOTTOM 5
   0.3x  #11 Numbered            1,200 views  9% non-follower   hold@3s 31%    2 sends
  ...

WHAT THE DATA SAYS
1. Hold at 3 seconds is the whole story. Top five average 66%, bottom five 33%.
   Everything else you are worried about is downstream of the first two seconds.
2. The posts where you were the one who looked bad: mean 8.1x vs 0.9x for
   everything else. n=5. Strongest signal here and it is not close.
3. Tool listicles get views and nothing else. High reach, no sends, no follows.
   Three of your bottom five.
4. Day of week shows nothing. Your Tuesday and Friday means are inside the
   noise. Stop optimising it.

STOP: listicles.
DO MORE: the ones with a cost you paid and a number attached.
```

Then hand the conclusions to `/ig-plan` so next week is built on the user's own
evidence rather than on defaults, and to `/ig-viral` so the swipe file gets
filtered to the formulas that work for this account specifically.
