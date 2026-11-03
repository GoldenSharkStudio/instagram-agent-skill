"""Write one eval case per prompt in prompts.json: evals/<skill>-<en|pt>-<n>/.

Each case checks the trigger only: the skill named in the table fires (`fired`)
and no other ig-* skill does (`only`). `min: 0` on `only` is needed, since a
tool_used grader with no `min` expects at least one call.

    python3 evals/build.py            # rewrite every case from the table
    claude plugin eval . --ablation none --runs 1 --no-publish --trust-plugin
"""
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = {"en": "en", "pt-BR": "pt"}
PROMPT = "---\nmax_turns: 2\nallowed_tools: [Read, Glob, Grep, Skill]\n---\n\n{text}\n"
FIRED = '---\ntype: tool_used\ntool: Skill\ninput_match: "{skill}\\\\b"\nmin: 1\n---\n'
ONLY = '---\ntype: tool_used\ntool: Skill\ninput_match: "ig-(?!{rest}\\\\b)"\nmin: 0\nmax: 0\n---\n'


def cases(table):
    """{case name: {file path relative to the case: content}}."""
    out = {}
    for skill, langs in table.items():
        rest = skill[len("ig-"):]
        for lang, prompts in langs.items():
            for n, text in enumerate(prompts, 1):
                out[f"{skill}-{TAG[lang]}-{n}"] = {
                    "prompt.md": PROMPT.format(text=text),
                    os.path.join("graders", "fired.md"): FIRED.format(skill=skill),
                    os.path.join("graders", "only.md"): ONLY.format(rest=rest),
                }
    return out


def main():
    with open(os.path.join(HERE, "prompts.json"), encoding="utf-8") as fh:
        table = json.load(fh)
    built = cases(table)
    for name in os.listdir(HERE):
        path = os.path.join(HERE, name)
        if os.path.isdir(path) and name.startswith("ig-") and name not in built:
            shutil.rmtree(path)
    for name, files in built.items():
        for rel, content in files.items():
            path = os.path.join(HERE, name, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
    print(f"{len(built)} cases")


if __name__ == "__main__":
    main()
