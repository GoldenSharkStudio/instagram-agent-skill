"""The pt-BR files that ship (fase 2, passos 4a.3 and 4a.4): ig-reel,
ig-caption, ig-viral and ig-human (the last one as a skeleton, see Human). The --lang nets plant their own pt-BR in a lone copy; this file is
about the real ones: the README hooks translated land in the same band as in
en, every pt-BR ask and dealbreaker fires on Portuguese, the figures read the
pt-BR way, and auto tells the two languages apart on the shipped stopwords."""

import glob
import io
import json
import os
import re
import shutil
import tempfile
import unicodedata
import unittest

from _support import SKILLS, fixture, load, read_fixture, run_json, run_tool

hs = load("hookscore")
bt = load("beats")
cp = load("caption")
dt = load("detect")
hz = load("humanize")

# The README ranking, en and its translation side by side: same verdict, same
# weakest property, same number of dealbreakers.
BANDS = [("STRONG", "SPECIFICITY", 0), ("STRONG", "ADDRESS", 0),
         ("OK", "STAKES", 2), ("WEAK", "FRONTLOAD", 1)]


def lines(name):
    return [l for l in read_fixture(name).splitlines() if l.strip()]


def shipped():
    """Every pt-BR file next to an en one, from the tree, not a list: the
    lang/ files and ig-human's slop.<code>.json."""
    out = []
    ens = glob.glob(os.path.join(SKILLS, "*", "lang", "en.json"))
    ens += glob.glob(os.path.join(SKILLS, "*", "slop.en.json"))
    for en in ens:
        pt = en[:-len("en.json")] + "pt-BR.json"
        if os.path.exists(pt):
            out.append((en, pt))
    return out


def folder_of(path):
    """The skill folder a shipped file sits in, lang/ or not."""
    folder = os.path.dirname(path)
    return os.path.basename(os.path.dirname(folder) if os.path.basename(folder) == "lang"
                            else folder)


# Dicts whose keys are names the language gives to its own rules (the
# inflection forms: en has s/ed/ing, pt-BR has 3s/past/ger), not a schema.
# Their content is checked by tests/test_inflection.py.
LANGUAGE_NAMED = ("suffixes", "families")


def shape(node, key=None):
    if key in LANGUAGE_NAMED:
        return "dict"
    if isinstance(node, dict):
        # `calibrated` is optional and only the skeleton lexicon carries it.
        return {k: shape(v, k) for k, v in node.items() if k not in ("note", "calibrated")}
    if isinstance(node, list):
        return "list"
    return type(node).__name__


class Files(unittest.TestCase):
    def test_the_four_folders_ship_pt_br(self):
        # ig-human ships two files (messages and lexicon), the others one.
        folders = sorted(folder_of(pt) for _, pt in shipped())
        self.assertEqual(folders, ["ig-caption", "ig-human", "ig-human", "ig-reel", "ig-viral"])

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
        with open(os.path.join(os.path.dirname(hs.__file__), "lang", "pt-BR.json"), encoding="utf-8") as fh:
            spoken = json.load(fh)["concrete"]["spoken_numbers"]
        self.assertNotIn("um", spoken)

    def test_stakes(self):
        L = hs.load_lang("pt-BR")
        self.assertEqual(hs.check_stakes("uma manhã tranquila", L)[0], 20.0)
        self.assertEqual(hs.check_stakes("nunca faça isso", L)[0], 70.0)
        self.assertEqual(hs.check_stakes("nunca pague R$ 5 nisso", L)[0], 100.0)
        # The rival is something on the line (seen in the real batch, 4b.4).
        for w in ("o concorrente postou", "os concorrentes da rua"):
            with self.subTest(w=w):
                self.assertEqual(hs.check_stakes(w, L)[0], 70.0)

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
    "Me chama no WhatsApp.",
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
        for (_, name, _), text in zip(L["ASKS"], ASKS):
            with self.subTest(text=text):
                self.assertEqual(cp.analyse(text, lang="pt-BR")["asks"], [name])

    def test_ask_ids_are_the_same_in_every_language(self):
        # The --json `ask_ids` is the contract a program reads; the
        # names are for people and translate. Same ids, same order, no repeat.
        ids = {}
        for path in glob.glob(os.path.join(SKILLS, "ig-caption", "lang", "*.json")):
            with open(path, encoding="utf-8") as fh:
                ids[os.path.basename(path)] = [a["id"] for a in json.load(fh)["caption"]["asks"]]
        self.assertGreaterEqual(len(ids), 2)
        self.assertEqual(len({tuple(v) for v in ids.values()}), 1, ids)
        one = next(iter(ids.values()))
        self.assertEqual(len(one), len(set(one)))
        self.assertTrue(all(re.fullmatch(r"[a-z_]+", i) for i in one), one)

    def test_json_ids_match_across_languages(self):
        en = cp.analyse("Comment CLAUSE below and save this.", lang="en")
        pt = cp.analyse("Comente CLÁUSULA e salve esse post.", lang="pt-BR")
        self.assertEqual(en["ask_ids"], ["comment_keyword", "save"])
        self.assertEqual(pt["ask_ids"], en["ask_ids"])
        self.assertNotEqual(pt["asks"], en["asks"])

    def test_english_asks_do_not_fire_in_pt(self):
        a = cp.analyse("Comment CLAUSE and save this. Link in bio.", lang="pt-BR")
        self.assertEqual(a["asks"], [])

    def test_portuguese_caption(self):
        proc, d = run_json("caption", fixture("caption.pt-BR.txt"),
                           "--keywords", "cláusula,preço de freela", "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(d["verdict"], "READY")
        self.assertEqual(d["asks"], ["comentar uma palavra"])
        self.assertEqual(d["ask_ids"], ["comment_keyword"])

    def test_generic_pt_tags(self):
        a = cp.analyse("Perdi R$ 5.\n\n#freela #sigamesigo #brasil", lang="pt-BR")
        details = {c["check"]: c["detail"] for c in a["checks"]}
        self.assertIn("2 delas genéricas", details["HASHTAGS"])

    def test_text_prints_portuguese(self):
        proc = run_tool("caption", fixture("caption.pt-BR.txt"), "--lang", "pt-BR")
        self.assertIn("REVISÃO DA LEGENDA", proc.stdout)
        self.assertIn("VEREDITO", proc.stdout)


class Swipe(unittest.TestCase):
    def test_english_batch_run_as_pt_br_is_unclassified(self):
        # pt-BR has its own `match` since 4b.4 (tests/test_hooks_pt_br.py);
        # an English batch read as Portuguese is named by none of them.
        proc, d = run_json("swipe", fixture("captured.tsv"), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ainda não tem `match`", proc.stderr)
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


PT_DRAFT = "good_draft.pt-BR.txt"

# One sample per pt-BR structural tell, in the order of the file: (id, text).
STRUCTURES = [
    ("not-just", "Não é só um contrato, é uma proteção."),
    ("not-only", "Não só protege o prazo, mas também o preço."),
    ("isnt-about", "Não se trata de contrato. É sobre confiança."),
    ("the-result", "O resultado? Zero retrabalho."),
    ("heres-what", "Aqui está o que eu aprendi com isso."),
    ("triad", "Rápido, simples e eficaz."),
    ("rocket", "Vem aí 🚀"),
    ("hashtag-wall", "#a #b #c #d #e"),
    ("as-an-ai", "Como um modelo de linguagem, eu não opino."),
    ("in-summary", "Em resumo, contrato bom é contrato claro."),
    ("engagement-bait", "Concorda?"),
    ("stop-scroll", "Pare de rolar agora."),
    ("in-this-video", "Neste vídeo eu vou te mostrar como cobrar."),
    ("emoji-bullets", "✅ Cláusula clara"),
    ("caps-shout", "ESSA REGRA MUDA TUDO"),
    ("follow-bait", "Segue pra mais dicas."),
    ("important-to", "É importante ressaltar que o prazo conta."),
    ("lets-dive", "Vamos mergulhar no assunto."),
    ("todays-world", "No mundo de hoje, tudo muda."),
    ("more-than-ever", "Isso importa mais do que nunca."),
]


def lexicon_copy(d, **changes):
    """slop.pt-BR.json with `changes` applied, written into d; returns the path."""
    with open(os.path.join(SKILLS, "ig-human", "slop.pt-BR.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    data.update(changes)
    path = os.path.join(d, "slop.pt-BR.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return path


class Human(unittest.TestCase):
    """ig-human in pt-BR is a skeleton: no words, no phrases, "calibrated":
    false. Until a corpus fills it, detect never says PASS."""

    def test_skeleton_shape(self):
        lex = dt.load_lexicon(lang="pt-BR")
        self.assertIs(lex["calibrated"], False)
        self.assertEqual((lex["words"], lex["phrases"]), ([], []))
        self.assertEqual(lex["lang"], "pt-BR")

    def test_en_is_calibrated_by_default(self):
        self.assertNotIn("calibrated", dt.load_lexicon(lang="en"))
        self.assertTrue(dt.is_calibrated(dt.load_lexicon(lang="en")))

    def test_good_pt_text_never_passes(self):
        proc, d = run_json("detect", fixture(PT_DRAFT), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(d["verdict"], "REVIEW")
        self.assertIs(d["calibrated"], False)
        self.assertEqual(d["structural_tells"], 0)

    def test_text_says_why(self):
        proc = run_tool("detect", fixture(PT_DRAFT), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("o léxico pt-BR ainda não está calibrado", proc.stdout)
        self.assertNotIn("Sinal mais fraco", proc.stdout)

    def test_the_cap_comes_from_the_flag(self):
        # Same text, same words, the flag flipped in a copy: it passes.
        with tempfile.TemporaryDirectory() as d:
            lex = lexicon_copy(d, calibrated=True)
            proc, out = run_json("detect", fixture(PT_DRAFT), "--lang", "pt-BR", "--lexicon", lex)
            self.assertEqual((proc.returncode, out["verdict"], out["calibrated"]), (0, "PASS", True))
            self.assertNotIn("calibrado", run_tool("detect", fixture(PT_DRAFT), "--lang", "pt-BR",
                                                   "--lexicon", lex).stdout)

    def test_calibrated_must_be_a_bool(self):
        with tempfile.TemporaryDirectory() as d:
            lex = lexicon_copy(d, calibrated="false")
            proc = run_tool("detect", fixture(PT_DRAFT), "--lexicon", lex)
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn("calibrated", proc.stderr)

    def test_en_is_unchanged(self):
        proc, d = run_json("detect", fixture("good_draft.txt"))
        self.assertEqual((proc.returncode, d["verdict"], d["calibrated"]), (0, "PASS", True))
        self.assertNotIn("calibrated", run_tool("detect", fixture("good_draft.txt")).stdout)

    def test_a_lexicon_without_the_key_is_calibrated(self):
        en = os.path.join(SKILLS, "ig-human", "slop.en.json")
        with open(en, encoding="utf-8") as fh:
            self.assertNotIn("calibrated", json.load(fh))
        proc, d = run_json("detect", fixture("good_draft.txt"), "--lexicon", en)
        self.assertEqual((proc.returncode, d["verdict"], d["calibrated"]), (0, "PASS", True))

    def test_uncalibrated_en_lexicon_is_held_too(self):
        # The cap is the flag's, not pt-BR's: a user's own lexicon can set it.
        with tempfile.TemporaryDirectory() as d:
            en = os.path.join(SKILLS, "ig-human", "slop.en.json")
            with open(en, encoding="utf-8") as fh:
                data = json.load(fh)
            data["calibrated"] = False
            path = os.path.join(d, "mine.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            proc = run_tool("detect", fixture("good_draft.txt"), "--lexicon", path)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("Held at REVIEW: the en lexicon is not calibrated yet", proc.stdout)

    def test_both_reasons_are_shown(self):
        results = {c: (90.0, "x") for c in dt.CHECKS}
        for lang, tell, calib in (("en", "structural tell(s) left", "not calibrated yet"),
                                  ("pt-BR", "sinal(is) estrutural(is) sobrando", "ainda não está calibrado")):
            out = io.StringIO()
            dt.render(results, 90.0, "REVIEW", out=out, tells=2, lang=lang,
                      calibrated=False, lexicon_lang=lang)
            with self.subTest(lang=lang):
                self.assertIn(tell, out.getvalue())
                self.assertIn(calib, out.getvalue())

    def test_every_structure_fires_on_its_sample(self):
        lex = dt.load_lexicon(lang="pt-BR")
        ids = [s["id"] for s in lex["structures"]]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids, [i for i, _ in STRUCTURES], "a new tell needs a sample, in file order")
        for (id_, text) in STRUCTURES:
            with self.subTest(id=id_):
                self.assertIn(id_, dt.count_tells(text, lex)[1])
                names = [f["name"] for f in hz.scan_structures(text, lex, "pt-BR")]
                self.assertIn(next(s["name"] for s in lex["structures"] if s["id"] == id_), names)

    def test_the_tells_do_not_fire_on_the_good_draft(self):
        self.assertEqual(dt.count_tells(read_fixture(PT_DRAFT), dt.load_lexicon(lang="pt-BR")), (0, []))

    def test_ia_the_verb_is_not_the_model(self):
        lex = dt.load_lexicon(lang="pt-BR")
        self.assertEqual(dt.count_tells("Como ia fazer isso sem prazo?", lex)[0], 0)
        self.assertEqual(dt.count_tells("Como uma IA eu não opino.", lex)[1], ["as-an-ai"])

    def test_tells_read_decomposed_accents(self):
        # An NFD paste ("é" as e + U+0301) counts like the composed text.
        lex = dt.load_lexicon(lang="pt-BR")
        for id_, text in STRUCTURES:
            nfd = unicodedata.normalize("NFD", text)
            with self.subTest(id=id_):
                self.assertEqual(dt.count_tells(nfd, lex), dt.count_tells(text, lex))
        accented = [t for _, t in STRUCTURES if unicodedata.normalize("NFD", t) != t]
        self.assertGreaterEqual(len(accented), 5, "the witness must carry accents")

    def test_humanize_cleans_and_rewrites_no_word(self):
        dirty = "Perdi\u200b R$\u00a018.000 \u2014 e “nunca” mais\u2026 Aceito isso.\n"
        proc = run_tool("humanize", "-", "--lang", "pt-BR", stdin=dirty)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, 'Perdi R$ 18.000, e "nunca" mais... Aceito isso.\n')
        words = lambda s: re.findall(r"[^\W\d_]+", s)
        self.assertEqual(words(proc.stdout), words(dirty))

    def test_humanize_flags_the_tells(self):
        proc = run_tool("humanize", "-", "--lang", "pt-BR", "--report",
                        stdin="No mundo de hoje, tudo muda.\n")
        self.assertIn("RELATÓRIO DO HUMANIZE", proc.stderr)
        self.assertIn("1 sinais estruturais", proc.stderr)

    def test_auto_picks_each_language_on_the_shipped_files(self):
        for tool in ("humanize", "detect"):
            for text, code in ((Auto.PT, "pt-BR"), (Auto.EN, "en")):
                with self.subTest(tool=tool, lang=code):
                    proc = run_tool(tool, "-", "--lang", "auto", stdin=text)
                    self.assertIn(f"lang: auto -> {code}", proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
