"""hooks.json pt-BR `match` (fase 4b, passo 4).

Every formula has a pt-BR regex, and every regex is held to phrases of its
form written from scratch in Portuguese (none copied from a real account).
The table is keyed by formula id, and the ids are read from hooks.json: a
formula added without pt-BR phrases breaks the net and is named. Each phrase
has to come out of `classify` as its own formula, walked in `classify_order`
like swipe does, so a pattern that steals another formula's hook shows up.
"""

import json
import os
import unicodedata
import unittest

from _support import SKILLS, fixture, load, run_json

sw = load("swipe")
HOOKS_PATH = os.path.join(SKILLS, "ig-reel", "hooks.json")

PT = {
    1: ["R$ 18.000 foi o que uma cláusula esquecida me custou.",
        "Essa vírgula me custou um cliente de dois anos.",
        "Perdi R$ 4 mil por não mandar um contrato."],
    2: ["Pare de postar três vezes por dia.",
        "Nunca mande orçamento por áudio.",
        "Não cobre por hora. Cobre por entrega."],
    3: ["Ninguém te conta que os primeiros 30 reels são para dar errado.",
        "O que ninguém fala sobre abrir empresa sozinho."],
    4: ["Essa ferramenta de R$ 60 substituiu o editor que eu pagava todo mês.",
        "Em vez de contratar um designer, eu uso isso."],
    5: ["Eu levava cinco horas numa proposta. Hoje levo vinte minutos.",
        "Agora leva 10 minutos para fechar o mês."],
    6: ["Postei um reel por dia durante 60 dias.",
        "Aqui estão os números de um mês inteiro de anúncio."],
    7: ["Você está escrevendo legenda errado, e a culpa não é sua.",
        "O maior erro de quem começa um negócio local."],
    8: ["Passei seis anos vendendo pacote de agência.",
        "A gente nunca contava isso para o cliente na reunião."],
    9: ["Roube este roteiro de quatro linhas.",
        "Copia essa mensagem de cobrança, ela funciona."],
    10: ["Se seus reels têm visualização e nenhum seguidor, assista até o fim.",
         "Se você atende pelo celular, isso é para você."],
    11: ["5 ajustes de legenda que dobram os salvamentos.",
         "OS 3 PIORES ERROS NA HORA DE ABRIR UMA LOJA",
         "Cinco perguntas que todo cliente faz antes de comprar."],
    12: ["\"Eu não quero aparecer na câmera.\" Tudo bem, aqui vai a versão sem rosto.",
         "“Está caro.” Beleza. Então faz a conta comigo."],
    13: ["Esse era o meu perfil em março. Esse é ele hoje.",
         "O antes e o depois da mesma vitrine, sem trocar nada caro."],
    14: ["Fotógrafos que cobram menos de R$ 2 mil: essa é a página que vocês evitam.",
         "Dentista, presta atenção nesse detalhe da agenda.",
         "Para quem atende em casa e nunca anuncia."],
    15: ["Meus primeiros 47 reels tiveram média de 300 visualizações.",
         "Os primeiros 12 clientes vieram de um lugar só."],
    16: ["Como eu posto todo dia sem odiar isso?",
         "Quanto custa um site que vende de verdade?",
         "Vale a pena anunciar com R$ 10 por dia?"],
    17: ["Carrossel versus reel: rodei os dois por 90 dias.",
         "Loja física x loja online, qual dá mais lucro",
         "A diferença entre seguidor e cliente."],
    18: ["Olha o que acontece quando eu colo a legenda do concorrente aqui.",
         "Deixa eu te mostrar o que essa planilha faz sozinha."],
    19: ["O preço muda no dia 15. Garanta o seu antes que acabe.",
         "Arrume as capas antes que a grade mude de novo."],
    20: ["Você não precisa de um nicho. Precisa de uma pessoa com nome.",
         "Não precisa ter equipe para vender todo dia."],
    21: ["...e foi aí que o cliente pediu o dinheiro de volta.",
         "E foi quando a sócia saiu da sala sem falar nada."],
    22: ["Trabalhar mais não significa ganhar mais.",
         "Ter muito seguidor não é garantia de venda.",
         "Cara legal termina em primeiro."],
    23: ["33% dos formados nunca mais leem um livro.",
         "80% das lojas fecham antes do quinto ano."],
    24: ["Esse é o novo celular da marca, e ele resolve o que eu odiava.",
         "Essa nova função do aplicativo muda o atendimento."],
    25: ["Teve um aluno que faturou um milhão em um mês.",
         "Um cliente meu que vendeu o carro para abrir a loja."],
    26: ["O jeito mais rápido de ganhar confiança é juntar provas.",
         "A melhor forma de responder cliente bravo é por escrito.",
         "Esta tem sido a maior procura do ano na loja."],
    27: ["Enquanto você posta todo dia, seu concorrente responde cada direct.",
         "Enquanto a maioria espera o cliente voltar, ela manda mensagem no dia seguinte.",
         "Enquanto uns reclamam do algoritmo, outros vendem pelo story."],
    28: ["Meu contador disse que eu não precisava de sistema. Fui testar.",
         "Disseram que post de manhã não vende. Testei por um mês.",
         "Todo mundo jura que hashtag morreu, então fui conferir."],
    29: ["Se eu fosse nutricionista, nunca pagaria um site antes de ter agenda.",
         "Se eu começasse uma loja hoje, faria só isso no primeiro mês.",
         "Se eu tivesse que começar do zero, eu faria assim."],
    30: ["Como vender pelo Instagram sem dançar na câmera.",
         "Como conseguir cliente sem pagar anúncio?",
         "Como eu dobrei as vendas sem contratar ninguém."],
}

# Things that are not hooks and must stay unclassified in pt-BR: the CTA, the
# follow ask, a line of hashtags, a caption that only feels something.
NOT_A_HOOK = [
    "Comenta PLANILHA que eu te mando o link no direct!",
    "Comente AULA para receber o acesso",
    "Me siga para mais vídeos como esse!",
    "Siga @fulano.teste",
    "#negocio #brasil #empreendedor",
    "🥹🤍",
    "Bom dia, gente bonita",
    "Que noite especial com a equipe toda",
    # "por" ends in "-or" like a group noun; the group is the first word.
    "É por isso que a gente continua aqui, todo dia, com o time.",
    # "Enquanto" and "Como ... sem" open the Contrast and the How-Without;
    # a connective and a figure of speech do not.
    "Enquanto isso, a equipe arruma a vitrine para amanhã.",
    "Como sempre, sem pressa e com café.",
]


def hooks():
    with open(HOOKS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["hooks"]


class PtBrFormulas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formulas = sw.load_formulas(HOOKS_PATH, "pt-BR")

    def test_every_formula_has_a_pt_br_regex(self):
        empty = [h["id"] for h in hooks() if not h["match"]["pt-BR"].strip()]
        self.assertEqual(empty, [], "formulas with no pt-BR match")

    def test_every_formula_has_pt_br_phrases(self):
        # Derived from hooks.json, never from this table: a new formula without
        # phrases here is a regex nobody has checked.
        ids = {h["id"] for h in hooks()}
        self.assertEqual(sorted(ids - set(PT)), [], "formulas with no pt-BR phrases")
        self.assertEqual(sorted(set(PT) - ids), [], "phrases for a formula that is gone")

    def test_each_phrase_names_its_own_formula(self):
        for fid, phrases in PT.items():
            for text in phrases:
                for shape, t in (("as written", text), ("CAPS", text.upper()),
                                 ("NFD", unicodedata.normalize("NFD", text))):
                    with self.subTest(id=fid, shape=shape, text=text):
                        self.assertEqual(sw.classify(t, self.formulas, "pt-BR")[0], fid)

    def test_a_cta_or_a_feeling_is_not_a_hook(self):
        for text in NOT_A_HOOK:
            with self.subTest(text=text):
                self.assertIsNone(sw.classify(text, self.formulas, "pt-BR")[0])

    def test_english_example_is_not_named_by_a_pt_br_regex_of_another_formula(self):
        # An English hook run as pt-BR may be unclassified, or named right by a
        # shape both languages share (a "%", a number up front); never wrong.
        for h in hooks():
            fid = sw.classify(h["example"], self.formulas, "pt-BR")[0]
            with self.subTest(id=h["id"], got=fid):
                self.assertIn(fid, (h["id"], None))


class Cli(unittest.TestCase):
    def test_swipe_names_pt_br_hooks(self):
        proc, d = run_json("swipe", fixture("captured.pt-BR.tsv"), "--lang", "pt-BR")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ainda não tem `match`", proc.stderr)
        named = [r["formula_id"] for r in d["reels"]]
        self.assertEqual(named, [9, 3, 1, None])


if __name__ == "__main__":
    unittest.main()
