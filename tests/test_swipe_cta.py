"""swipe.py: a captured "hook" that is a call to action, not a hook.

On an outlier reel the hook is often on the cover, and the first line of the
caption is "Follow for more" or a row of hashtags. swipe flags those rows so
the user recaptures the cover text instead of learning from a CTA. The flag
is a warning only: ranking, formulas and medians do not change.

The patterns live in lang/<code>.json, section swipe.cta, one list per
language. Every phrase below is written from scratch. The negative net is
derived: every hooks.json example and on-screen line (en) and every pt-BR
phrase in test_hooks_pt_br.PT is a real hook shape and must not be flagged.
"""

import json
import os
import shutil
import tempfile
import unittest

from _support import SKILLS, fixture, load, run_json, run_tool
from test_hooks_pt_br import PT

sw = load("swipe")
VIRAL = os.path.join(SKILLS, "ig-viral")
HOOKS_PATH = os.path.join(SKILLS, "ig-reel", "hooks.json")

CTA = {
    "en": [
        "Follow for more tips like this",
        "Follow @someaccount for part 2",
        "Comment GUIDE and I will send it",
        "Comment below what you would add",
        "Comment “plan” to get the template",
        "Save this for later",
        "Share this with a friend who needs it",
        "Tag someone who does this every Monday",
        "DM me the word START",
        "Link in bio for the full checklist",
        "Grab the link in my bio",
        "#smallbusiness #marketing #reels",
        "@studio #behindthescenes",
        "Subscribe for the next one",
    ],
    "pt-BR": [
        "Siga @umperfil para mais dicas",
        "Segue a gente pra parte 2",
        "Comenta GUIA que eu te mando",
        "Comente aqui embaixo o que faltou",
        "Comenta eu quero e recebe o roteiro",
        "Salva esse post pra não esquecer",
        "Salve este vídeo para depois",
        "Compartilha com quem precisa ouvir isso",
        "Manda pra aquela amiga que vive atrasada",
        "Marca alguém que faz isso toda segunda",
        "Me chama no direct que eu explico",
        "Chama no zap pra orçamento",
        "Link na bio com o passo a passo",
        "Clica no link da bio",
        "#empreendedorismo #marketingdigital",
    ],
}

# Hooks that start with the same verbs and are not calls to action.
NOT_CTA = {
    "en": [
        "Save $500 a month with one boring habit",
        "Follow these three steps before you hire anyone",
        "Comment sections are where your next client is hiding",
        "Share prices dropped and nobody in my group noticed",
        "Tag lines are the most expensive six words you will write",
        "Nobody tells you that your first 30 reels are supposed to flop",
        "I lost $18,000 because of one missing contract",
        "The link between price and trust is not what you think",
    ],
    "pt-BR": [
        "Salve, galera: hoje o assunto é preço",
        "Segue o raciocínio: cliente barato custa caro",
        "Marca registrada não protege o que você acha que protege",
        "Manda bem quem cobra antes de começar",
        "Compartilhar a tela na reunião me custou um cliente",
        "Comentei uma vez e perdi o contrato",
        "Ninguém te conta que os primeiros 30 reels são para dar errado",
    ],
}


def patterns(lang):
    with open(os.path.join(VIRAL, "lang", lang + ".json"), encoding="utf-8") as fh:
        return json.load(fh)["swipe"]["cta"]


def hooks_json_en():
    with open(HOOKS_PATH, encoding="utf-8") as fh:
        hooks = json.load(fh)["hooks"]
    out = []
    for h in hooks:
        for key in ("example", "on_screen"):
            v = h.get(key)
            out += v if isinstance(v, list) else [v] if v else []
    return [v for v in out if isinstance(v, str)]


class Patterns(unittest.TestCase):
    def test_each_language_has_its_list(self):
        for lang in ("en", "pt-BR"):
            with self.subTest(lang=lang):
                cta = patterns(lang)
                self.assertIsInstance(cta, list)
                self.assertGreater(len(cta), 3)
                self.assertTrue(all(isinstance(p, str) and p for p in cta))

    def test_flags_every_cta(self):
        for lang, lines in CTA.items():
            for line in lines:
                with self.subTest(lang=lang, line=line):
                    self.assertTrue(sw.is_cta(line, lang), "not flagged")

    def test_leaves_hooks_alone(self):
        for lang, lines in NOT_CTA.items():
            for line in lines:
                with self.subTest(lang=lang, line=line):
                    self.assertFalse(sw.is_cta(line, lang), "flagged a hook")

    def test_no_hooks_json_sample_is_flagged(self):
        samples = hooks_json_en()
        self.assertGreater(len(samples), 30)            # the scan reached the data
        flagged = [s for s in samples if sw.is_cta(s, "en")]
        self.assertEqual(flagged, [])

    def test_no_pt_br_formula_phrase_is_flagged(self):
        phrases = [p for ps in PT.values() for p in ps]
        self.assertGreater(len(phrases), 50)
        flagged = [p for p in phrases if sw.is_cta(p, "pt-BR")]
        self.assertEqual(flagged, [])

    def test_no_borrowing_between_languages(self):
        # A Portuguese CTA is not an English one, and the other way round.
        self.assertFalse(sw.is_cta("Comenta GUIA que eu te mando", "en"))
        self.assertFalse(sw.is_cta("Save this for later", "pt-BR"))

    def test_curly_quote_and_nfd(self):
        self.assertTrue(sw.is_cta("Comment “plan” to get it", "en"))
        nfd = "Marca alguém que faz isso".replace("é", "é")
        self.assertTrue(sw.is_cta(nfd, "pt-BR"))


def write_tsv(d, rows):
    path = os.path.join(d, "c.tsv")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("account\tmedian\tviews\thook\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")
    return path


ROWS = [("@a", "1000", "40000", "nobody tells you that your first 30 reels are supposed to flop"),
        ("@b", "1000", "30000", "Follow for more tips like this"),
        ("@c", "1000", "2000", "steal this four line follow up it took me two years")]


class Output(unittest.TestCase):
    def test_json_marks_each_reel_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            proc, a = run_json("swipe", write_tsv(d, ROWS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual({r["account"]: r["cta"] for r in a["reels"]},
                         {"@a": False, "@b": True, "@c": False})
        self.assertEqual(a["cta"], 1)

    def test_flag_changes_no_number(self):
        # Decision: a warning, not a filter. The CTA row is still ranked,
        # classified and counted in the medians.
        with tempfile.TemporaryDirectory() as d:
            _, a = run_json("swipe", write_tsv(d, ROWS))
        self.assertEqual([r["account"] for r in a["reels"]], ["@a", "@b", "@c"])
        self.assertEqual(a["n"], 3)
        self.assertEqual(a["unclassified"], 1)

    def test_render_marks_the_row_and_sums_up(self):
        with tempfile.TemporaryDirectory() as d:
            out = run_tool("swipe", write_tsv(d, ROWS)).stdout
        lines = out.splitlines()
        i = next(n for n, l in enumerate(lines) if "Follow for more" in l)
        self.assertIn("call to action", lines[i + 1])
        self.assertEqual(sum("call to action" in l for l in lines), 2)   # the row + the summary
        self.assertIn("1 of 3", next(l for l in lines if l.lstrip().startswith("call to action:")))

    def test_render_pt_br(self):
        rows = [("@a", "1000", "40000", "Ninguém te conta que os primeiros 30 reels são para dar errado"),
                ("@b", "1000", "30000", "Comenta GUIA que eu te mando")]
        with tempfile.TemporaryDirectory() as d:
            out = run_tool("swipe", write_tsv(d, rows), "--lang", "pt-BR").stdout
        self.assertIn("chamada para ação", out)
        self.assertNotIn("call to action", out)

    def test_no_cta_no_summary_line(self):
        # The README block has no CTA, so its output does not change.
        out = run_tool("swipe", fixture("captured.tsv")).stdout
        self.assertNotIn("call to action", out)
        _, a = run_json("swipe", fixture("captured.tsv"))
        self.assertEqual(a["cta"], 0)
        self.assertTrue(all(r["cta"] is False for r in a["reels"]))

    def test_markdown_notes_the_row(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "swipe.md")
            proc = run_tool("swipe", write_tsv(d, ROWS), "--out", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(out, encoding="utf-8") as fh:
                md = fh.read()
        blocks = md.split("\n## ")
        flagged = [b for b in blocks if "call to action" in b]
        self.assertEqual(len(flagged), 1)
        self.assertIn("Follow for more", flagged[0])


class BrokenData(unittest.TestCase):
    """The cta list ships next to the messages; a broken one fails closed."""

    def copy_with(self, d, mutate):
        dst = os.path.join(d, "ig-viral")
        shutil.copytree(VIRAL, dst)
        path = os.path.join(dst, "lang", "en.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        mutate(data)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return os.path.join(dst, "swipe.py")

    def test_missing_list_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            script = self.copy_with(d, lambda data: data["swipe"].pop("cta"))
            proc = run_tool(script, fixture("captured.tsv"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("en.json", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_bad_regex_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            script = self.copy_with(d, lambda data: data["swipe"]["cta"].append("(unclosed"))
            proc = run_tool(script, fixture("captured.tsv"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("en.json", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
