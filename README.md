# The Instagram agent skill

Fourteen Claude skills that run an Instagram account. Free, MIT, no signup, no
API key, nothing to connect.

One of them writes your Reels off 30 hook formulas and scores the hook before
you waste a take on it. One goes and finds the reels that are actually working
in your niche and ranks them by how far each beat its own account. One writes
the caption and shows you exactly what the feed shows before the "... more".
One scores your profile out of 100 and rewrites what lost points. One plans the
week.

And one is the humanizer, which is the reason the rest are usable. It strips
the em dashes, the slop vocabulary and the invisible watermark characters out
of a draft, then scores what is left against a five-check panel before you ever
see it.

**Nothing gets posted until you say yes.** These skills write. You post.

## Install

Paste this into Claude:

```
https://github.com/GoldenSharkStudio/instagram-agent-skill

Install this skill, then run /ig-setup.
```

Or do it yourself, in Claude Code:

```bash
git clone https://github.com/GoldenSharkStudio/instagram-agent-skill.git
cp -r instagram-agent-skill/skills/ig-* ~/.claude/skills/
```

Or as a plugin:

```
/plugin marketplace add GoldenSharkStudio/instagram-agent-skill
/plugin install instagram-agent
```

Project-local instead of global: copy the same folders into your repo's
`.claude/skills/`. No Claude Code at all? Paste any single `SKILL.md` at the top
of a chat and it runs as a mode. You lose the five Python tools, which is most
of the point of `/ig-reel` and `/ig-human`, but the rest works.

Then run `/ig-setup`: ten minutes, once. It writes `~/.claude/instagram/voice.md`
with you, from three of your own reels or a short interview. By hand works too:
copy `templates/voice.en.md` (or `templates/voice.pt-BR.md` if you post in
Portuguese) to `~/.claude/instagram/voice.md` and fill it in. Every skill reads
that file. It matters more here than on other platforms, because you have to
say the words out loud.

## The fourteen

| command | what it does |
| --- | --- |
| `/ig-setup` | Start here. Writes your `voice.md` with you, from three of your own posts or a short interview, and picks the language your posts are checked in. |
| `/ig-reel` | One idea into a Reel. Three hooks from [30 formulas](skills/ig-reel/hooks.json), scored, then the script, the on-screen text and a timed beat sheet. |
| `/ig-viral` | Goes and finds what is working in your niche, ranks it by multiple over each account's own median, names the formula, writes the swipe file. |
| `/ig-caption` | The caption, linted. Shows you the 125 characters the feed actually shows before the tap. |
| `/ig-carousel` | Swipe posts. The cover that earns the swipe, slide copy, and the 1080x1350 files. |
| `/ig-story` | The daily story sequence, which sticker does which job, and the DM funnel that starts with them moving first. |
| `/ig-profile` | Scores your profile against a [12-part rubric](skills/ig-profile/rubric.json) out of 100, then rewrites in fix-first order. |
| `/ig-plan` | The week. What to post, which format, when, and the 10 accounts to engage with. |
| `/ig-human` | The humanizer. Two scripts that actually run. See below. |
| `/ig-comment` | Comments on other people's posts. Nine types, picked by what the post actually is. Never "🔥🔥🔥". |
| `/ig-reply` | The thread under your own post. Sorts into keyword / lead / substance / question / support / noise, then writes in that order. |
| `/ig-dm` | The keyword delivery, the first message, the collab pitch, and the two follow-ups. Two. |
| `/ig-repurpose` | One video, podcast or newsletter into a week of reels and carousels that each stand alone. |
| `/ig-audit` | Post-mortem on what you already posted. Ranks by outlier multiple and sends per reach, not views. |

## The five tools that actually run

No dependencies, no network, nothing uploaded. They run on your machine, on
your text.

Every tool takes `--lang`: `en` (the default), `pt-BR` or `auto`, which guesses
from the text and says on stderr what it picked. The skills pass the
**Language:** line of your `voice.md`. `en` ships for every tool. `pt-BR` ships
for every tool, with one gap: the pt-BR humanizer has no
calibrated lexicon yet. `words` and `phrases` are empty, so it strips invisible
characters, fixes typography and flags the structural tells, but it replaces no
word, and `detect` never gives PASS in pt-BR until the lexicon is calibrated:
it stops at REVIEW and says why (`"calibrated": false` in `--json`). A language
whose files are not there is refused with exit 2 and the missing file's name,
never a silent fall back to English.

### Hooks

```bash
python3 hookscore.py hooks.txt              # rank your options
python3 beats.py script.txt --target 30     # time it before you shoot it
```

```
HOOK RANKING
==============================================================================
->  85.6 STRONG  Nobody tells you that your first 30 reels are supposed to f...
        weakest: SPECIFICITY (75)
    81.4 STRONG  I lost $18,000 because of one missing contract.
        weakest: ADDRESS (70)
    54.4 OK      Stop scrolling if you want to grow on Instagram in 2026 🔥
        weakest: STAKES (70)
        dealbreaker: Opens with "stop scrolling". Asking for attention proves
                     you have not earned it.
        dealbreaker: Emoji in the hook. On-screen text at hook size has room
                     for words or for an emoji, not both.
     9.6 WEAK    Hey guys, today I wanted to talk about content strategy
        weakest: FRONTLOAD (0)
        dealbreaker: Greeting. Nobody came to the feed to be greeted.
```

`beats.py` estimates how long each line takes to say, stacks them into
timecodes, and flags the four things that kill a Reel in the edit: a hook that
runs past three seconds, a beat long enough for the viewer to leave, a run of
lines with nothing concrete in them, and no loop back to the first line.

```
BEAT SHEET  ·  73 words  ·  ~26.6s at 165 wpm  ·  target 30s
========================================================================
  0:00.0   2.9s  HOOK    I lost $18,000 because of one missing contract.
  0:02.9  14.6s  MID     Here is the exact clause I now put in every single...
                         ^ 14.6s on one beat
  0:17.4   2.9s          Section 4. Payment on delivery, not on approval.
  0:20.4   2.9s          Approval is a feeling. Delivery is a date.
  0:23.3   3.3s  CTA     That one word change is worth $18,000 to me.
------------------------------------------------------------------------
  - Beat(s) 2 run past 4s. Either split the line or change what is on screen
    inside it. A static frame is where people leave.
  - Loops: the last beat repeats "$18,000" from the hook. Second watches are
    free reach.
  - 3.5s under target. Either add 9 words or shoot it short. Short is usually
    right.
```

### The caption

```bash
python3 caption.py caption.txt --keywords "client contracts,freelance pricing"
```

Instagram gives a caption about 125 characters in the feed and hides the rest
behind a tap. Almost every caption that fails, fails there. So the first thing
this prints is that window, as a box, the way a scrolling stranger reads it:

```
  WHAT THE FEED SHOWS
  +------------------------------------------------------+
  | I lost $18,000 because of one missing clause in a    |
  | contract, and the worst part is that I had read the  |
  | thing twice before I si                              |
  +-------------------------------------------- ... more +

  PASS  LENGTH            389 / 2200 characters
  WARN  FIRST LINE        133 characters, so it gets cut at 125 mid-thought. Fine if the cut is a cliffhanger, bad if it is a subordinate clause
  PASS  HOOK IS CONCRETE  2 number(s) or name(s) in the visible window
  PASS  HASHTAGS          3 tag(s): #freelance #contracts #agencyowner
  PASS  TAG PLACEMENT     tags are below the fold
  PASS  LINKS             no dead links in the body
  PASS  ONE ASK           one call to action: comment a keyword
  PASS  EMOJI             0 emoji, 0.0 per 100 characters
  WARN  SEARCH TERMS      1/2 present, 0 in the visible window. Missing: client contracts
```

It enforces the current hashtag cap, which is **five per post**, not thirty.
Instagram cut it on 18 December 2025.

### The humanizer

```bash
python3 humanize.py draft.txt --report      # clean it, show every change
python3 detect.py draft.txt                  # score it, five checks
python3 detect.py before.txt after.txt       # prove the delta
```

**What comes out automatically:**

- **Invisible characters.** Zero-width spaces and joiners, word joiners, soft
  hyphens, byte-order marks, Unicode tag characters, invisible separators,
  non-breaking and narrow spaces. Your keyboard does not make these. They
  survive copy-paste and they are invisible in every editor you own.
- **Typography.** Em dash to comma, en dash to hyphen, curly quotes to
  straight, ellipsis to three dots, and the orphaned punctuation that leaves.
- **The lexicon.** 243 stock words and phrases with plain-English replacements.
  The last block of it is Instagram-specific: "stop scrolling", "in today's
  video", "follow for more", "tag someone who needs this", "the algorithm
  loves", "run don't walk". A replacement keeps the sentence grammatical: the
  article agrees with the new word ("an innovative format" becomes "a new
  format"), a word can take a different replacement by use ("Skyrocket your
  sales" becomes "Boost your sales", "Sales skyrocketed" becomes "Sales shot
  up"), and a use no plain word fits ("an empowering talk") is kept and flagged
  for a rewrite. It lives in
  [`slop.en.json`](skills/ig-human/slop.en.json) and it is meant to be edited.

**What gets flagged instead of fixed:** "It's not just X, it's Y", rule-of-three
triads, the video preamble, emoji bullet lists, three shouted words in a row,
hashtag walls, reflex follow bait, uniform sentence length, and a stock phrase
with a clause hanging on it (deleting "follow for more" from "Follow for more if
you love design." would leave "If you love design."). Changing the shape
of a sentence needs judgement, so those come back for a rewrite rather than
getting mangled by a regex.

Run against a caption written to be as bad as possible
([`tests/fixtures/bad_draft.txt`](tests/fixtures/bad_draft.txt)):

```
  BURSTINESS    #######################.  95.7    variation 0.68 across 10 sentences
  SPECIFICITY   ###########.............  47.7    3.1 concrete markers per 100 words
  SLOP DENSITY  ........................   0.0    17 stock terms, 17.7 per 100 words
  FINGERPRINT   ############............  49.7    2 em dash
  VOICE         ############............  50.8    13 structural tells
  ------------------------------------------------------------
  HUMAN SCORE   #######.................  29.3   FLAGGED
```

After `humanize.py`, with the flagged structures still unrewritten. The score
clears 70, but it stops at REVIEW, not PASS: while a structural tell is left
(the triads, the rocket bullets, the hashtag wall) the verdict waits for a
person:

```
  29.3 FLAGGED  ->  74.4 REVIEW   (+45.1)
```

### The swipe file

```bash
python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
```

Raw views are not evidence. A 2,000,000-follower account doing 400,000 views
had a quiet Tuesday. A 4,000-follower account doing 400,000 views found
something. `swipe.py` ranks on the multiple over each account's own median,
names the hook formula, and prints what separates the top third from the
bottom third.

```
SWIPE FILE  ·  4 reels  ·  4 accounts  ·  baseline: account median
==============================================================================
    60.0x  hook  57  #9  The Steal              @c                 180,000
           "steal this four line follow up it took me two years"
    37.5x  hook  86  #3  Nobody Tells You       @a                 412,000
           "nobody tells you that your first 30 reels are supposed to flop"
     3.5x  hook  81  #1  Cost Confession        @d                  21,000
           "I lost $18,000 because of one missing contract"
     1.3x  hook  13  -   unclassified           @b               1,200,000
           "in this video I am going to show you my morning routine"
```

### From another program

```bash
python3 -m igtools hookscore --hook "You lose $400 a month on this" --json
python3 -m igtools caption caption.txt --keywords "reels,hooks" --lang pt-BR --json
```

`igtools/` puts the six tools behind one command and one Python import, for a
program that wants a gate before it publishes anything (caption READY, hook
70 or more, humanizer PASS). It holds none of their code: it runs each
script's own `main()` from the `skills/` folder beside it, so a skill folder
copied alone still works and there is no second copy to drift. Carry the repo
whole (a git subtree under any prefix is enough) and point `PYTHONPATH` at it,
or run from its root. Without `skills/` it stops with exit 2 and names the path.

The command takes the script's arguments and gives the script's output and
exit code. Every `--json` object carries `"schema": 1`; in a list, each
element does. The same from Python:

```python
import igtools
igtools.score_hook("Você perde R$400 por mês nisso", lang="pt-BR")["verdict"]
igtools.lint_caption(text, keywords=["reels"], lang="pt-BR")
igtools.beat_sheet(script, target=30), igtools.humanize(draft), igtools.detect(draft)
igtools.rank_swipe(tsv_text)
```

Each function returns the dict the script prints with `--json`. A verdict
(exit 1) is in the dict; a refusal (exit 2: empty text, language data that
does not load, a path that cannot be read) raises `igtools.Error` with the
tool's message. The functions swap `sys.stdin`/`stdout` while a tool runs, so
call them from one thread, or use the command.

### Tests

```bash
python3 -m unittest discover tests
```

stdlib only, like the tools. The example blocks above are golden tests: their
inputs live in [`tests/fixtures/`](tests/fixtures/), and changing a tool's
output without updating this README fails the suite. So does adding a term to
`slop.en.json` or a formula to `hooks.json` without updating the counts quoted here.

## What I actually measured, which is the part worth reading

I did not want to publish a hook scorer on the claim that it feels right, so I
tested it. The corpus is **74 real short-form hooks**: the first three seconds
of the auto-caption track from the top eight and bottom eight performing shorts
on each of five channels, view counts from 931 to 550,000.

They are YouTube Shorts rather than Reels, because Instagram does not hand you
view counts you can collect without logging into somebody's account, and
scraping it would violate the Terms this repo tells you not to violate. The
hook grammar is the same and the sourcing is public. That is a real limitation
and it is stated here rather than buried.

**Three results, two of them uncomfortable:**

**1. It catches bad hooks well.** Against ten hooks written deliberately badly,
AUC 0.83, and nine of the ten scored below the median of the real corpus. If
your hook opens on a greeting, a preamble or nothing concrete, this tells you.

**2. It does not pick winners.** Separating a good creator's hits from that
same creator's misses: **AUC 0.56, where 0.50 is a coin flip.** Of the five
checks, only SPECIFICITY separated the bands meaningfully, by 60 points of
median. STAKES and ADDRESS had identical medians in both bands, which means on
this corpus they measured nothing.

So the honest use is: kill the obviously weak hooks before you shoot them, then
trust your own retention graph. Nothing that reads text can tell you which of
two decent hooks will travel, because that is decided by your face, your edit,
your audio and who Instagram shows it to.

**3. The formula classifier was broken and the test is what caught it.** The
`match` regexes in `hooks.json` were written off my own templates, and they
named **8%** of real hooks. People do not speak in templates. Rewriting them
against actual transcribed speech took it to **49%**, and four formulas went
into the set because they kept appearing and were not there: Contrarian Flip,
The Statistic, The Reveal, Someone Else's Result, plus The Superlative. On the
other 51% it abstains, which is correct: a lot of short-form is podcast clips
that have no hook formula at all.

One fixed bug worth naming: `SPECIFICITY` only counted digits, so "zero
dollars" and "three marketing books" scored as having nothing concrete in them.
Spoken hooks say their numbers out loud.

If you re-run this on a bigger or cleaner corpus and get a different answer, I
would rather know. The measurement script is not in the repo because it depends
on `yt-dlp`, but the method is four lines and is written out in
[`/ig-viral`](skills/ig-viral/SKILL.md).

## The fine print, which is the honest part

**These skills do not post to Instagram.** There is a real Content Publishing
API for Professional accounts, and it needs a Meta developer app, a linked
Page, a long-lived token and app review, which is not a thing a skill can hand
you. Everything else people use to automate posting, commenting, following or
DMing is browser automation or a third-party tool, and both violate
[Instagram's Terms of Use](https://help.instagram.com/581066165581870) and get
accounts action-blocked. So every skill here ends the same way: a copy-ready
block, and you post it. That is not a limitation bolted on afterwards, it is
the design, and it is why the approval gate is real rather than a setting.

The one exception is keyword auto-replies in DMs, which Instagram supports
through its own tools and approved partners, and which only fire after somebody
comments first. `/ig-dm` says where that line is.

**`/ig-viral` reads, it does not scrape.** Ten accounts, a dozen reels each, at
human speed, with you driving your own browser. It never asks for your password
and never logs in as you. Automated collection at volume is the thing that gets
accounts restricted, and a crawler is not what this is.

**The five detection checks are local heuristics, not detector APIs.** They are
modelled on the signals public detectors key on and they run entirely on your
machine. They are not GPTZero, Originality, Copyleaks, Winston or Turnitin,
they do not call those services, and they cannot promise those verdicts. Fixing
what they measure tends to move those numbers, because they are measuring the
same underlying things. That is the whole claim. Nobody can honestly sell you
"undetectable", and anybody who does is selling you something.

**The invisible-character pass is real and it is narrow.** It removes the
zero-width and format characters that end up in generated text and survive a
copy-paste. That is a genuine, checkable fingerprint. It is not a claim about
defeating a cryptographic watermarking scheme, and this repo does not make one.

**Nothing here fabricates.** No invented metrics, clients or outcomes go under
your name. If a draft needs a number you have not given, it comes back with
`{{your number}}` in it and a flag, every time.

**Platform numbers go stale.** The hashtag cap moved from 30 to 5 in December
2025 while this repo was being written, and the linter had the old number in it
until the fact got checked. If something here contradicts what Instagram is
doing when you read it, Instagram is right.

## Files

```
igtools/                           the six tools as one command and one import, for a program
                                   (runs the scripts in skills/, holds none of their code)
skills/ig-reel/hooks.json          30 hook formulas: template, example, on-screen line,
                                   what it is for, how it gets ruined, and a match regex
                                   per language (an empty one never matches)
skills/ig-reel/lang/en.json        the words hookscore and beats know (stakes, openers, numbers)
                                   and every sentence they print
skills/ig-reel/lang/pt-BR.json     the same in Portuguese
skills/ig-reel/hookscore.py        the five-property hook panel
skills/ig-reel/beats.py            script to timed beat sheet
skills/ig-caption/lang/en.json     the calls to action and the generic hashtags it knows,
                                   and every sentence it prints
skills/ig-caption/lang/pt-BR.json  the same in Portuguese
skills/ig-caption/caption.py       the truncation preview and the caption linter
skills/ig-human/slop.en.json       the lexicon: 243 terms, 18 invisible classes, 16 tells
skills/ig-human/slop.pt-BR.json    the same in Portuguese, as a skeleton: structural tells and
                                   voice, no terms yet, "calibrated": false
skills/ig-human/lang/en.json       every sentence humanize and detect print (not the lexicon, so
                                   --lexicon never swaps them)
skills/ig-human/lang/pt-BR.json    the same in Portuguese
skills/ig-human/humanize.py        the three cleaning passes
skills/ig-human/detect.py          the five-check panel
skills/ig-viral/lang/en.json       every sentence swipe prints, and the patterns of a CTA row
skills/ig-viral/lang/pt-BR.json    the same in Portuguese
skills/ig-viral/swipe.py           outlier ranking and formula classification
skills/ig-profile/rubric.json      the 100-point profile score
skills/ig-setup/voice.*.md         copies of the two forms below, so /ig-setup works alone
templates/voice.en.md              your voice profile. Fill this in first.
templates/voice.pt-BR.md           the same form in Portuguese
templates/log.md                   the line the skills append to log.md, and read back
```

## Credit

Made by Jake Schincariol, [opusjake.ai](https://opusjake.ai).

This repository is an independent fork maintained by
[GoldenSharkStudio](https://github.com/GoldenSharkStudio). It keeps the
original skills and adds Brazilian Portuguese (pt-BR) support alongside
English, a test suite, and an importable library for the scorers. Changes
are tracked in the git history; the original work stays MIT and credited
above.

Sibling repo, same idea for a different platform:
[linkedin-agent-skill](https://github.com/Jakeschincariol/linkedin-agent-skill).

## License

MIT. Take it, change it, ship it.
