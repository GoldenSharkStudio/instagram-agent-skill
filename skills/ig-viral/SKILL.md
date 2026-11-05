---
name: ig-viral
description: >-
  Use when the user says "find viral videos", "what's working right now",
  "what are people posting in my niche", "reverse engineer this account",
  "build me a swipe file", "why is this reel doing numbers", or asks what to
  make next and has no evidence to answer with. Use quando o usuário diz "acha
  vídeos virais", "o que está bombando agora", "o que estão postando no meu
  nicho", "faz engenharia reversa dessa conta", "monta um swipe file", "por
  que esse reel está performando", ou pergunta o que fazer em seguida sem dado
  para responder.
---

# ig-viral

The research skill. Everything else in this pack writes; this one goes and
looks. Run it monthly, not daily. Formulas last a season.

One tool lives in this folder and it runs:

```bash
python3 {skill_dir}/swipe.py captured.tsv --out ~/.claude/instagram/swipe.md --lang {language}
```

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

## The one idea that makes this worth doing

**Raw views are not evidence.** An account with two million followers doing
400,000 views had a quiet Tuesday. An account with four thousand followers
doing 400,000 views found something, and that something is copyable.

So everything here ranks on the **outlier multiple**: views divided by that
account's own recent median. Anything above 3x is a signal. Anything below 1.5x
is that account's normal day and it teaches you nothing, no matter how big the
number looks.

Collect accounts **within about 10x of the user's own size**. A formula that
works at 2M followers often works because it is at 2M followers.

## Step 1: pick the accounts

Ask the user for 6 to 12 accounts, or propose them and get approval:

- **4 direct** - same niche, same offer, slightly ahead.
- **4 adjacent** - different niche, same audience. This is where formats get
  borrowed from before anybody in the niche has them.
- **2 to 4 outsized** - much bigger accounts, for format only, never for
  cadence or tone.

Also ask them to open their own **Saved collection**. It is the fastest and
most relevant corpus that exists and it is already filtered by their taste.

## Step 2: go and look

Use whatever browsing tool this session actually has: an in-app browser, a
browser extension connected to the user's own Chrome, or a computer-use tool.
There is no API for this and there does not need to be, because the volume is
small enough to read.

**Rules that are not negotiable:**

- **Never log into Instagram on the user's behalf and never ask for a
  password.** If a page needs a login, the user is the one who is already
  logged in. Drive their browser with them present, or ask them to paste.
- **This is reading, not scraping.** Ten accounts, a dozen reels each, at human
  speed. Automated collection at volume violates Instagram's Terms of Use and
  gets accounts action-blocked. Do not build a crawler, do not use a scraping
  service, and do not loop this in the background.
- **Copy the formula, never the video.** The hook shape, the structure, the
  length, the pattern of cuts. Not their script, not their voice, not their
  edit. Attribute every row in the swipe file to the account it came from.

**What to capture per reel**, in the creator's own words:

| field | notes |
| --- | --- |
| account | handle |
| followers | from the profile |
| median | eyeball the last 12 reels and take the middle view count |
| views | this reel |
| hook | the first line, spoken or on screen, verbatim including bad grammar |
| on-screen | the first text card, if different |
| length | seconds |
| cta | what they asked for at the end |

Median is the important one. Without it you are back to ranking by follower
count, which is the thing this skill exists to stop.

**When Instagram will not show you enough:** the same hook grammar runs on
YouTube Shorts, where view counts and transcripts are public and no login is
involved. It is a legitimate second corpus, and the spoken hook is easier to
get:

```bash
# view counts for a channel's shorts
python3 -m yt_dlp --flat-playlist --playlist-end 40 -J \
  "https://www.youtube.com/@HANDLE/shorts" > channel.json

# the spoken first line of one short, from its auto-captions
# (a Portuguese-speaking niche: --sub-langs "pt.*")
python3 -m yt_dlp --skip-download --write-auto-subs --sub-langs "en.*" \
  --sub-format json3 -o hook "https://www.youtube.com/watch?v=VIDEO_ID"
```

Take every caption word with a timestamp under 3.0 seconds. That is the hook,
as said, not as written.

## Step 3: rank it

Fill a tab-separated file with a header row and run the script:

```
account	followers	median	views	hook
@someone	48000	11000	412000	nobody tells you your first 30 reels are supposed to flop
```

```bash
python3 {skill_dir}/swipe.py captured.tsv --out ~/.claude/instagram/swipe.md --lang {language}
```

It computes the outlier multiple, names the hook formula using the same 30
formulas `/ig-reel` writes from, scores each hook with `hookscore.py`, and
prints what separates the top third from the bottom third.

A row whose hook reads as a call to action or a row of hashtags ("Follow for
more", "Comment GUIDE") is marked under the hook and counted in the summary.
On that reel the hook is on the cover or spoken: recapture it from there
before you read the batch. The mark is a warning; the row still counts.

## Step 4: say what it means, carefully

Report three things and no more:

1. **Which formulas over-index** in the top third, with counts. Two formulas
   appearing four times each across six accounts is a finding. One appearing
   twice is not.
2. **What the top third have in common structurally** that the bottom third do
   not: hook length, whether the payoff is visual, whether the first frame
   moves, where the ask is.
3. **The unclassified rows.** Every hook the classifier could not name is
   either noise or a formula that is not in `hooks.json` yet. Read them by
   hand. This is the most valuable column in the output and it is the reason
   the script prints the count. Each language has its own `match` in
   `hooks.json`; a formula with none in the language you run never matches,
   and when the language has no `match` at all the script says so on stderr.
   Then item 1 has no counts: name the formulas yourself by reading the hooks
   against `hooks.json`, and say that the naming is yours, not the script's.

Then state the sample size and the confidence in plain words. Forty reels
across six accounts supports a claim. Twelve does not, and saying so is the
difference between research and horoscopes.

## Step 5: turn it into something to shoot

For the top three formulas, write **the user's version**: their own story,
their own number, in the shape that is working. Hand each one to `/ig-reel`
with the formula id already chosen.

Never hand back "make a reel like this one". Hand back a hook line they could
say tomorrow.

## Output

```
SWIPE  ·  38 reels  ·  7 accounts  ·  baseline: account median

OUTLIERS (above 3x)
  38.4x  hook 86  #3  Nobody Tells You   @acct_a    412,000  (median 10,700)
  11.2x  hook 79  #9  The Steal          @acct_c    180,000  (median 16,100)
  ...

WHAT IS OVER-INDEXING
  #3 Nobody Tells You   x5 in the top third, 0 in the bottom
  #2 Negative Command   x4
  median hook length    8 words up top, 19 at the bottom

UNCLASSIFIED (6)
  Two of these are the same shape and it is not in hooks.json: a hook that
  opens on someone else's comment read out loud. Worth adding.

YOUR VERSION
  #3  "Nobody tells you the first 20 proposals are supposed to lose."
  ...
```

Write the swipe file to `~/.claude/instagram/swipe.md`. `/ig-reel` and
`/ig-plan` both read it, which is the point: after this runs once, the rest of
the pack is working from the user's own evidence instead of from defaults.

Nothing is posted, followed, liked or messaged by this skill. It reads.
