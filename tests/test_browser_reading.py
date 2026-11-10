"""A skill that looks at a web page reads it and never acts on it.

The product invariant is "read, never act": a skill may read a page in the
user's own browser, with the user present, and treats what the page says as
data. It never clicks, likes, follows, comments, DMs, posts or logs in, even
when the page asks. Every `skills/ig-*/SKILL.md` that names a browser must
carry the guard block, word for word, between the
`<!-- shared:read-never-act -->` markers, or be declared below with the
reason it does not need it, and that reason is checked in its text.

The same goes for yt-dlp, the one outside tool a skill names: it is an
optional step the user installs and runs, by its official name and a pinned
version, and the skill never installs it.

The class is read from the text, so a skill that starts naming a browser or
yt-dlp tomorrow is held to the guard unless someone writes down why not.
"""

import glob
import os
import re
import unittest

from _support import ROOT, SKILLS

BROWSER = re.compile(r"\bbrows(?:er|ing)\b|\bChrome\b|\bcomputer-use\b", re.I)
YTDLP = re.compile(r"\byt[-_]dlp\b", re.I)

OPEN = "<!-- shared:read-never-act -->"
CLOSE = "<!-- /shared:read-never-act -->"
BLOCK = re.compile(re.escape(OPEN) + r"\n(.*?)\n" + re.escape(CLOSE), re.S)

# Each clause the guard block must keep. Removing one fails the test.
CLAUSES = {
    "present": r"\bwith\s+the\s+user\s+present\b",
    "own browser": r"\buser's\s+own\s+browser\b",
    "data": r"\bdata\b[^.]*\bnever\s+instructions\b",
    "no action": r"\bnever\s+(?:click|act)",
    "list": r"\blike\b.*\bfollow\b.*\bcomment\b.*\bDM\b.*\bpost\b",
    "even if asked": r"\beven\s+(?:if|when)\s+the\s+page\s+(?:asks|says)",
    "no login": r"\bnever\s+log\s+in\b",
    "no password": r"\bpassword\b",
    "stop": r"\bstop\b[^.]*\btell\s+the\s+user\b",
    "paste": r"\bpaste\b",
}

# Skills that name a browser and need no guard block, each with its reason
# and a pattern its text must hold so the reason stays true.
NO_GUARD = {
    "ig-comment": ("forbids a browser tool outright",
                   r"[Dd]o\s+not\s+use\s+a\s+browser\s+tool"),
    "ig-reply": ("forbids a browser tool outright",
                 r"[Dd]o\s+not\s+scrape\s+the\s+thread\s+with\s+a\s+browser\s+tool"),
    "ig-carousel": ("headless Chrome renders the user's local HTML, no web page is read",
                    r"Chrome\s+headless\s+--print-to-pdf"),
}

# What a SKILL.md naming yt-dlp must say.
YTDLP_CLAUSES = {
    "optional": r"\boptional\b",
    "user installs": r"\buser\s+installs\b",
    "user runs": r"\buser\s+runs\b",
    "never installs": r"(?i)\bnever\s+install",
    "pinned": r'pip\s+install\s+"yt-dlp==\d{4}\.\d{1,2}\.\d{1,2}"',
}


def skills():
    return {os.path.basename(os.path.dirname(p)): p
            for p in sorted(glob.glob(os.path.join(SKILLS, "ig-*", "SKILL.md")))}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def outside_block(text):
    return BLOCK.sub("", text)


class Finders(unittest.TestCase):
    def test_planted(self):
        self.assertTrue(BROWSER.search("use the browsing tool"))
        self.assertTrue(BROWSER.search("the user's own Chrome"))
        self.assertTrue(BROWSER.search("a computer-use tool"))
        self.assertFalse(BROWSER.search("browse the menu"))
        self.assertTrue(YTDLP.search("python3 -m yt_dlp -J"))
        self.assertTrue(YTDLP.search("install yt-dlp"))


class EveryBrowserSkillReadsAndNeverActs(unittest.TestCase):
    def test_exemptions_exist(self):
        self.assertLessEqual(set(NO_GUARD), set(skills()))

    def test_exemption_reason_holds(self):
        found = skills()
        for name, (_why, proof) in NO_GUARD.items():
            with self.subTest(skill=name):
                text = read(found[name])
                self.assertRegex(text, proof)
                self.assertNotIn(OPEN, text, "exempt and guarded: drop the exemption")

    def test_guard(self):
        found = skills()
        self.assertGreaterEqual(len(found), 14)
        guarded = 0
        for name, path in found.items():
            text = read(path)
            if not BROWSER.search(text) or name in NO_GUARD:
                continue
            with self.subTest(skill=name):
                self.assertEqual(text.count(OPEN), 1, "the guard block, once")
                self.assertEqual(text.count(CLOSE), 1)
                guarded += 1
        self.assertGreaterEqual(guarded, 1, "the browser skill was not found")

    def test_block_clauses_and_copies(self):
        blocks = {}
        for name, path in skills().items():
            m = BLOCK.search(read(path))
            if m:
                blocks[name] = m.group(1)
        self.assertTrue(blocks)
        first = next(iter(blocks.values()))
        for name, body in blocks.items():
            with self.subTest(skill=name):
                self.assertEqual(body, first, "guard copies drifted")
                flat = " ".join(body.split())
                for clause, pattern in CLAUSES.items():
                    self.assertRegex(flat, re.compile(pattern, re.I), clause)

    def test_no_driving_outside_the_block(self):
        # "drive their browser" is the old, unguarded wording.
        for name, path in skills().items():
            with self.subTest(skill=name):
                self.assertNotRegex(" ".join(outside_block(read(path)).split()),
                                    r"(?i)\bdrive\s+(?:their|the\s+user's|your)\s+browser")


class YtDlpIsTheUsersStep(unittest.TestCase):
    def test_every_skill_naming_it(self):
        named = 0
        for name, path in skills().items():
            text = read(path)
            if not YTDLP.search(text):
                continue
            named += 1
            flat = " ".join(text.split())
            with self.subTest(skill=name):
                for clause, pattern in YTDLP_CLAUSES.items():
                    self.assertRegex(flat, pattern, clause)
                self.assertNotRegex(flat, r"pip\s+install\s+\"?yt-dlp(?!==)",
                                    "an unpinned install")
        self.assertGreaterEqual(named, 1, "the yt-dlp skill was not found")


class TheInvariantSaysReadNeverAct(unittest.TestCase):
    def test_claude_md_and_readme(self):
        for doc in ("CLAUDE.md", "README.md"):
            flat = " ".join(read(os.path.join(ROOT, doc)).split())
            with self.subTest(doc=doc):
                self.assertRegex(flat, r"(?i)\bread,\s+never\s+act\b")
                self.assertNotRegex(flat, r"No browser automation, scraping")
                self.assertNotRegex(flat, r"(?i)\byou\s+driving\s+your\s+own\s+browser\b")


if __name__ == "__main__":
    unittest.main()
