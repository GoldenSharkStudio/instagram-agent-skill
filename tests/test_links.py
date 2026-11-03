"""Every regex that recognizes a link in user text takes the same links.

Members are found in the source, not listed: any module-level `*_RE` whose
pattern holds "https?://". caption counts what it finds (LINK_RE); humanize
shields it from every rewrite (URL_RE). A bare domain with a two-level country
TLD ("loja.com.br/x", typed without a scheme in Brazilian captions) used to
slip through both: caption did not count it and humanize rewrote inside it.
"""

import ast
import re
import unittest

from _support import TOOLS, load

# Links as people type them in a caption, each with the exact span to take.
LINKS = [
    "https://x.com/a",
    "http://loja.com.br/oferta",
    "www.loja.com.br",
    "loja.com/x",
    "loja.com.br/x",
    "minha-loja.com.br/oferta-de-natal",
    "shop.co.uk/sale",
    "app.io/",
]
# Text that is not a link and must stay out.
NOT_LINKS = ["Vendas.com", "R$1.500,00", "e.g. this", "fim.de frase", "loja.com.br"]


def link_regexes():
    """(tool, name) for every module-level `X_RE = re.compile("...https?://...")`."""
    out = []
    for tool, path in sorted(TOOLS.items()):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                continue
            call = node.value
            if not (isinstance(call.func, ast.Attribute) and call.func.attr == "compile"
                    and call.args and isinstance(call.args[0], ast.Constant)):
                continue
            if "https?://" in str(call.args[0].value):
                out.extend((tool, t.id) for t in node.targets if isinstance(t, ast.Name))
    return out


class LinkNet(unittest.TestCase):
    def test_members_are_found(self):
        # The guard cannot be satisfied by an empty net: both known members show.
        self.assertTrue({("caption", "LINK_RE"), ("humanize", "URL_RE")} <= set(link_regexes()))

    def test_every_member_takes_every_link_whole(self):
        for tool, name in link_regexes():
            rx = getattr(load(tool), name)
            for link in LINKS:
                with self.subTest(tool=tool, regex=name, link=link):
                    m = rx.search(f"Compre em {link} hoje")
                    self.assertIsNotNone(m)
                    self.assertEqual(m.group(0), link)

    def test_no_member_takes_a_non_link(self):
        for tool, name in link_regexes():
            rx = getattr(load(tool), name)
            for text in NOT_LINKS:
                with self.subTest(tool=tool, regex=name, text=text):
                    self.assertIsNone(rx.search(text))


class Behaviour(unittest.TestCase):
    """What the user sees: counted by caption, untouched by humanize."""

    def test_caption_counts_bare_country_domain(self):
        a = load("caption").analyse("Link: loja.com.br/x and shop.com/y")
        self.assertEqual(a["links"], ["loja.com.br/x", "shop.com/y"])

    def test_humanize_never_rewrites_inside_a_bare_link(self):
        hz = load("humanize")
        lex = hz.load_lexicon()
        for link in ("loja.com.br/leverage", "shop.com/unlock", "app.io/empower"):
            with self.subTest(link=link):
                out, _ = hz.humanize(f"Get it at {link} today.", lex)
                self.assertIn(link, out)

    def test_witness_needs_the_link_rule(self):
        # The terms in the paths above are lexicon entries: without the shield
        # humanize does rewrite them, so the test above can fail.
        hz = load("humanize")
        out, _ = hz.humanize("We leverage it and unlock it and empower it.", hz.load_lexicon())
        for term in ("leverage", "unlock", "empower"):
            self.assertNotIn(term, out)


if __name__ == "__main__":
    unittest.main()
