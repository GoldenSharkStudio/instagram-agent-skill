"""python3 -m igtools <tool> [the tool's own arguments]"""

import os
import sys

if __package__ in (None, ""):                 # run as a path: find the package beside it
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from igtools import TOOLS, Error, load  # noqa: E402

USAGE = ("usage: python3 -m igtools <tool> [arguments]\n"
         f"tools: {', '.join(TOOLS)}\n"
         "Each tool takes its script's own arguments; add --json for a program.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        print(USAGE)
        sys.exit(0)
    if not argv or argv[0] not in TOOLS:
        if argv:
            print(f"igtools: no tool named {argv[0]!r}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    tool = argv[0]
    try:
        mod = load(tool)
    except Error as err:
        print(err, file=sys.stderr)
        sys.exit(2)
    sys.argv = [f"igtools {tool}", *argv[1:]]
    mod.main()


if __name__ == "__main__":
    main()
