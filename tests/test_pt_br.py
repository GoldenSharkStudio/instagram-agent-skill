"""The pt-BR files that ship (fase 2, passo 4a.3): ig-reel, ig-caption and
ig-viral. The --lang nets plant their own pt-BR in a lone copy; this file is
about the real ones: the README hooks translated land in the same band as in
en, every pt-BR ask and dealbreaker fires on Portuguese, the figures read the
pt-BR way, and auto tells the two languages apart on the shipped stopwords."""

import glob
import json
import os
import unittest

from _support import SKILLS, fixture, load, read_fixture, run_json, run_tool

hs = load("hookscore")
bt = load("beats")
cp = load("caption")

# The README ranking, en and its translation side by side: same verdict, same
# weakest property, same number of dealbreakers.
BANDS = [("STRONG", "SPECIFICITY", 0), ("STRONG", "ADDRESS", 0),
         ("OK", "STAKES", 2), ("WEAK", "FRONTLOAD", 1)]


def lines(name):
    return [l for l in read_fixture(name).splitlines() if l.strip()]


def shipped():
    """Every pt-BR file next to an en one, from the tree, not a list."""
    out = []
    for en in glob.glob(os.path.join(SKILLS, "*", "lang", "en.json")):
        pt = en[:-len("en.json")] + "pt-BR.json"
        if os.path.exists(pt):
            out.append((en, pt))
    return out


def shape(node):
    if isinstance(node, dict):
        return {k: shape(v) for k, v in node.items() if k not in ("note",)}
    if isinstance(node, list):
        return "list"
    return type(node).__name__


class Files(unittest.TestCase):
    def test_the_three_folders_ship_pt_br(self):
        folders = sorted(os.path.basename(os.path.dirname(os.path.dirname(pt)))
                         for _, pt in shipped())
        self.assertEqual(folders, ["ig-caption", "ig-reel", "ig-viral"])

    def test_same_keys_as_en(self):
        for en, pt in shipped():
            with self.subTest(file=pt), open(en, encoding="utf-8") as a, \
                    open(pt, encoding="utf-8") as b:
                ja, jb = json.load(a), json.load(b)
                self.assertEqual(jb["lang"], "pt-BR")
                self.assertEqual(shape(ja), shape(jb))

    def test_auto_stopwords_are_one_list(self):
        lists = {}
        for _, pt in shipped():
            with open(pt, encoding="utf-8") as fh:
                d = json.load(fh)
            if "auto" in d:
                lists[pt] = d["auto"]["stopwords"]
        self.assertGreaterEqual(len(lists), 2)
        self.assertEqual(len({tuple(v) for v in lists.values()}), 1, lists)

    def test_auto_stopwords_are_not_english_words(self):
        # A pt stopword that is also an English word ("a", "no", "do") would
        # count for pt-BR on every English text.
        with open(os.path.join(SKILLS, "ig-reel", "lang", "en.json"), encoding="utf-8") as fh:
            en = json.load(fh)
        english = set(en["beats"]["stopwords"]) | set(en["auto"]["stopwords"]) | {"a", "no", "do", "as"}
        with open(os.path.join(SKILLS, "ig-reel", "lang", "pt-BR.json"), encoding="utf-8") as fh:
            pt = json.load(fh)["auto"]["stopwords"]
        self.assertEqual(sorted(set(pt) & english), [])


class Hooks(unittest.TestCase):
    def test_translation_lands_in_the_same_band(self):
        en, pt = lines("hooks.txt"), lines("hooks.pt-BR.txt")
        self.assertEqual(len(en), len(pt))
        for a, b, (verdict, weakest, flags) in zip(en, pt, BANDS):
            with self.subTest(hook=b):
                ra, _, va, fa = hs.run(a, "en")
                rb, _, vb, fb = hs.run(b, "pt-BR")
                self.assertEqual((va, vb), (verdict, verdict))
                self.assertEqual(min(hs.CHECKS, key=lambda c: rb[c][0]), weakest)
                self.assertEqual((len(fa), len(fb)), (flags, flags))

    def test_dealbreakers_speak_portuguese(self):
        _, _, _, flags = hs.run("Pare de rolar se você quer crescer no Instagram em 2026 🔥", "pt-BR")
        self.assertIn('"pare de rolar"', flags[0])
        self.assertIn("Emoji no gancho", flags[1])
        _, _, _, flags = hs.run("Oi gente, hoje eu queria falar sobre conteúdo", "pt-BR")
        self.assertEqual(flags, ["Cumprimento. Ninguém abriu o feed para ser cumprimentado."])
        _, _, _, flags = hs.run("Neste vídeo vou te mostrar 3 cláusulas", "pt-BR")
        self.assertIn("Preâmbulo", flags[0])

    def test_every_dealbreaker_fires_on_its_sample(self):
        samples = ["Pare de rolar agora", "Neste vídeo eu explico", "Olá, tudo bem?"]
        L = hs.load_lang("pt-BR")
        own = L["DEALBREAKERS"][:len(samples)]
        self.assertEqual(len(L["DEALBREAKERS"]) - 2, len(samples), "a new dealbreaker needs a sample")
        for (pattern, _), text in zip(own, samples):
            with self.subTest(text=text):
                self.assertTrue(pattern.search(text))

    def test_greeting_needs_a_whole_word(self):
        # "Oi" opens a greeting; "Oito" is a number.
        _, _, _, flags = hs.run("Oito contratos e nenhum assinado", "pt-BR")
        self.assertEqual(flags, [])

    def test_portuguese_drops_the_subject(self):
        # "Perdi" is first person with no "eu" in sight.
        L = hs.load_lang("pt-BR")
        self.assertEqual(hs.check_address("Perdi R$ 18.000 num contrato", L)[0], 70.0)
        self.assertEqual(hs.check_address("Você perde R$ 18.000", L)[0], 100.0)
        self.assertEqual(hs.check_address("Salve este contrato", L)[0], 90.0)
        self.assertEqual(hs.check_address("O cliente sumiu", L)[0], 35.0)

    def test_spoken_numbers_and_money(self):
        L = hs.load_lang("pt-BR")
        self.assertGreater(hs.check_specificity("vinte mil reais jogados fora", L)[0],
                           hs.check_specificity("muita coisa jogada fora", L)[0])
        # "um" is an article, not a quantity, as "one" is not in en.
        self.assertNotIn("um", L["SPOKEN_NUMBERS"])

    def test_stakes(self):
        L = hs.load_lang("pt-BR")
        self.assertEqual(hs.check_stakes("uma manhã tranquila", L)[0], 20.0)
        self.assertEqual(hs.check_stakes("nunca faça isso", L)[0], 70.0)
        self.assertEqual(hs.check_stakes("nunca pague R$ 5 nisso", L)[0], 100.0)

    def test_ranking_prints_portuguese(self):
        proc = run_tool("hookscore", fixture("hooks.pt-BR.txt"), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RANKING DE GANCHOS", proc.stdout)
        self.assertIn("mais fraca:", proc.stdout)


class Figures(unittest.TestCase):
    def test_pt_br_figure_is_one_word(self):
        # "R$ 18.000" is "R$" and one figure, as "$18,000" is one word in en.
        for mod in (hs, bt):
            with self.subTest(tool=mod.__name__):
                self.assertEqual(mod.words("R$ 18.000 e 3,5x"), ["R$", "18000", "e", "35x"])
                self.assertEqual(mod.words("$18,000"), ["$18000"])
                self.assertEqual(mod.words("Seção 4. Pagamento"), ["Seção", "4", "Pagamento"])

    def test_loop_shows_the_figure_the_language_writes(self):
        proc = run_tool("beats", fixture("script.pt-BR.txt"), "--target", "30", "--lang", "pt-BR")
        self.assertIn('repete "18.000" do gancho', proc.stdout)
        en = run_tool("beats", fixture("script.txt"), "--target", "30")
        self.assertIn('repeats "$18,000" from the hook', en.stdout)

    def test_beat_sheet_prints_portuguese(self):
        proc = run_tool("beats", fixture("script.pt-BR.txt"), "--target", "30", "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ROTEIRO POR BATIDAS", proc.stdout)
        self.assertIn("abaixo da meta", proc.stdout)


# One sample per pt-BR ask, in the order of the file. Each must fire its own
# ask and no other.
ASKS = [
    "Comente CONTRATO que eu te mando.",
    "Me chama no direct.",
    "Salve esse post.",
    "Compartilhe com quem precisa.",
    "Me siga pra mais.",
    "O link na bio tem tudo.",
    "Arraste pro lado.",
    "Me conta nos comentários.",
]


class Caption(unittest.TestCase):
    def test_every_ask_fires_alone(self):
        L = cp.load_lang("pt-BR")
        self.assertEqual(len(L["ASKS"]), len(ASKS), "a new ask needs a sample")
        for (_, name), text in zip(L["ASKS"], ASKS):
            with self.subTest(text=text):
                self.assertEqual(cp.analyse(text, lang="pt-BR")["asks"], [name])

    def test_english_asks_do_not_fire_in_pt(self):
        a = cp.analyse("Comment CLAUSE and save this. Link in bio.", lang="pt-BR")
        self.assertEqual(a["asks"], [])

    def test_portuguese_caption(self):
        proc, d = run_json("caption", fixture("caption.pt-BR.txt"),
                           "--keywords", "cláusula,preço de freela", "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(d["verdict"], "READY")
        self.assertEqual(d["asks"], ["comentar uma palavra"])

    def test_generic_pt_tags(self):
        a = cp.analyse("Perdi R$ 5.\n\n#freela #sigamesigo #brasil", lang="pt-BR")
        details = {c["check"]: c["detail"] for c in a["checks"]}
        self.assertIn("2 delas genéricas", details["HASHTAGS"])

    def test_text_prints_portuguese(self):
        proc = run_tool("caption", fixture("caption.pt-BR.txt"), "--lang", "pt-BR")
        self.assertIn("REVISÃO DA LEGENDA", proc.stdout)
        self.assertIn("VEREDITO", proc.stdout)


class Swipe(unittest.TestCase):
    def test_pt_br_runs_and_names_no_formula(self):
        proc, d = run_json("swipe", fixture("captured.tsv"), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ainda não tem `match` para pt-BR", proc.stderr)
        self.assertTrue(all(r["formula_id"] is None for r in d["reels"]))
        self.assertTrue(all(r["hook_score"] is not None for r in d["reels"]))

    def test_text_prints_portuguese(self):
        proc = run_tool("swipe", fixture("captured.tsv"), "--lang", "pt-BR")
        self.assertIn("O QUE ESTÁ FUNCIONANDO NESTE LOTE", proc.stdout)


class Auto(unittest.TestCase):
    PT = "Você não sabe o que a gente perdeu com isso, mas é muito mais do que parece.\n"
    EN = "You have no idea what we lost on this, and it is a lot more than it looks.\n"

    def test_picks_each_language_on_the_shipped_files(self):
        for tool in ("hookscore", "beats", "caption", "swipe"):
            for text, code in ((self.PT, "pt-BR"), (self.EN, "en")):
                with self.subTest(tool=tool, lang=code):
                    if tool == "hookscore":
                        proc = run_tool(tool, "--hook", text.strip(), "--lang", "auto")
                    elif tool == "swipe":
                        proc = run_tool(tool, "-", "--lang", "auto",
                                        stdin=f"views\thook\n1000\t{text.strip()}\n")
                    else:
                        proc = run_tool(tool, "-", "--lang", "auto", stdin=text)
                    self.assertIn(f"lang: auto -> {code}", proc.stderr)


if __name__ == "__main__":
    unittest.main()
