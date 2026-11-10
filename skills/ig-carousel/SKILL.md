---
name: ig-carousel
description: >-
  Use when the user says "carousel", "slides", "swipe post", "turn this into a
  carousel", or has a list-shaped or step-shaped idea that would die as a
  single image. Use quando o usuário diz "carrossel", "slides", "post de
  arrastar", "transforma isso em carrossel", ou tem uma ideia em lista ou em
  passos que morreria numa imagem só.
---

# ig-carousel

Carousels are the highest-dwell format on the grid, because a swipe is an
interaction and a scroll is not. They also get a second chance: Instagram can
show a carousel again starting from a later slide to someone who did not engage
the first time, so slide two has to stand on its own as well.

The format rewards one idea broken into steps. It punishes a caption cut into
pieces.

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

## When to use it instead of a Reel

Use a carousel when the idea has **sequence and needs to be re-read**: steps, a
framework with parts, a before and after, a list worth screenshotting. Use a
Reel when the idea has motion, a face, or a payoff that has to be seen
happening.

If the idea is one claim, it is neither. Hand it to `/ig-reel` and say so.

## Structure

6 to 10 slides. The cap is 20 and 20 is almost always a book nobody finishes.
Under 5 and the swipe never starts.

```
1         COVER     the hook. 6 words or fewer, at a size that is legible in
                    the grid at thumbnail. One line of promise under it.
2         THE STAKE why this matters, in one sentence. This slide is also a
                    second cover, so it cannot be setup.
3 to N    ONE IDEA PER SLIDE. A headline of 3 to 7 words, at most 25 words
                    under it. If a slide needs a paragraph, it is two slides.
N+1       RECAP     the whole thing as a list. This is the screenshot slide.
LAST      CTA       one action. Save, comment a keyword, or follow. One.
```

## Slide copy rules

- **The cover is 80% of the result.** Six words. Big. Nothing on the deck saves
  a cover nobody swipes.
- **Design for the grid crop.** The profile grid crops to a portrait rectangle
  that is taller than it is wide, and the exact ratio has moved more than once.
  Build at 1080x1350 and keep the cover text well inside the middle, clear of
  the outer 120 pixels on every side, and the crop stops mattering.
- **Number the slides** (3/8). Completion goes up when people can see the end.
- **No slide is a paragraph.** If it cannot be said in 25 words, split it.
- **The recap slide is the one people screenshot and send.** Sends are the
  strongest signal you can earn. Make it standalone and readable with no
  context.
- **The handle on every slide**, small, bottom corner. Screenshots travel
  without you.
- **Alt text on the cover at minimum.** It is read by screen readers and by
  Instagram.

## Building the files

Instagram wants 1080x1350 (4:5), JPEG or PNG, up to 20 items. Build it as HTML
and print each slide:

```bash
# one <section> per slide, 1080x1350, page-break-after: always
# then Chrome headless --print-to-pdf, or any HTML-to-image you already use
```

Write the HTML with `width:1080px; height:1350px`, a single accent colour, and
type no smaller than 32px, because this is read on a phone at a third of its
real size. If the project has a brand skill or a design system, use it and do
not invent a palette.

## Output

The slide-by-slide copy first, as a numbered list the user can read in ten
seconds and edit before anything is rendered. Then the **caption**, which for a
carousel is Job B in `/ig-caption`: the caption is doing work here, because the
cover has already used its six words.

Run both through `/ig-human`. Build the files only after the user approves the
copy.

```
CAROUSEL  ·  8 slides

1  COVER   THE $18,000 CLAUSE
           One line I now put in every contract.
2  STAKE   I approved the work. They asked for the money back nine days later.
3          WHAT IT SAYS
           Payment on delivery, not on approval.
...
7  RECAP   All four lines, in order.
8  CTA     Comment CONTRACT and I will send the full clause.

Caption: Job B, hook in line 1, one ask, 3 tags.
```

Nothing is uploaded. The user posts it. When they approve the copy, append one
line to `~/.claude/instagram/log.md` (create it if it is missing), type
`carousel`, with the cover line as `first line`, so `/ig-audit` and `/ig-plan`
see it:

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
