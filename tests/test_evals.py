"""The trigger evals (evals/) are built from evals/prompts.json by
evals/build.py. Three prompts in English and three in Portuguese per skill,
each case checks that its skill fires and no other ig-* skill does."""
import importlib.util
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALS = os.path.join(ROOT, "evals")
SKILLS = sorted(d for d in os.listdir(os.path.join(ROOT, "skills")) if d.startswith("ig-"))

spec = importlib.util.spec_from_file_location("build", os.path.join(EVALS, "build.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

with open(os.path.join(EVALS, "prompts.json"), encoding="utf-8") as fh:
    TABLE = json.load(fh)


def field(text, key):
    m = re.search(rf'^{key}:\s*"?(.*?)"?$', text, re.M)
    return m.group(1) if m else None


def grader_regex(text):
    # the YAML double-quoted scalar holds "\\b"; YAML reads it as \b
    return re.compile(field(text, "input_match").replace("\\\\", "\\"))


def calls(skill):
    """How the Skill tool input can name a skill: bare, or plugin-qualified."""
    return [json.dumps({"skill": skill}), json.dumps({"skill": f"instagram-agent:{skill}"})]


class Table(unittest.TestCase):
    def test_every_skill_three_prompts_per_language(self):
        self.assertEqual(sorted(TABLE), SKILLS)
        for skill, langs in TABLE.items():
            with self.subTest(skill=skill):
                self.assertEqual(sorted(langs), ["en", "pt-BR"])
                self.assertEqual([len(p) for p in langs.values()], [3, 3])

    def test_prompts_distinct_and_not_empty(self):
        every = [p for langs in TABLE.values() for ps in langs.values() for p in ps]
        self.assertTrue(all(p.strip() for p in every))
        self.assertEqual(len(every), len(set(every)))


class CasesOnDisk(unittest.TestCase):
    def test_disk_matches_the_table(self):
        built = build.cases(TABLE)
        on_disk = sorted(d for d in os.listdir(EVALS) if d.startswith("ig-"))
        self.assertEqual(on_disk, sorted(built), "run python3 evals/build.py")
        for name, files in built.items():
            for rel, content in files.items():
                with self.subTest(case=name, file=rel):
                    with open(os.path.join(EVALS, name, rel), encoding="utf-8") as fh:
                        self.assertEqual(fh.read(), content, "run python3 evals/build.py")

    def test_only_grader_has_explicit_min_zero(self):
        # without min, tool_used expects >= 1 call and "no other skill" always fails
        for name, files in build.cases(TABLE).items():
            only = files[os.path.join("graders", "only.md")]
            self.assertEqual((field(only, "min"), field(only, "max")), ("0", "0"), name)


class GraderRegexes(unittest.TestCase):
    """Run each case's regexes against the Skill input of every skill."""

    def test_fired_matches_its_skill_only(self):
        for skill in SKILLS:
            files = build.cases({skill: {"en": ["x"]}})[f"{skill}-en-1"]
            fired = grader_regex(files[os.path.join("graders", "fired.md")])
            for other in SKILLS:
                with self.subTest(case=skill, call=other):
                    hits = [bool(fired.search(c)) for c in calls(other)]
                    self.assertEqual(hits, [other == skill] * 2)

    def test_only_matches_every_other_skill(self):
        for skill in SKILLS:
            files = build.cases({skill: {"en": ["x"]}})[f"{skill}-en-1"]
            only = grader_regex(files[os.path.join("graders", "only.md")])
            for other in SKILLS:
                with self.subTest(case=skill, call=other):
                    hits = [bool(only.search(c)) for c in calls(other)]
                    self.assertEqual(hits, [other != skill] * 2)


if __name__ == "__main__":
    unittest.main()
