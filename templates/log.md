# log.md

`~/.claude/instagram/log.md` is the history of what went out. The skills append
to it when the user approves a draft and read it back to plan, audit and pace.
Nothing in it is posted anywhere. You do not need to copy this file: the first
skill that logs something creates `log.md` with this shape.

Every skill that uses the log carries the block below word for word, so a skill
folder copied on its own still writes lines the others can read.

<!-- shared:log-schema -->
One line per item, oldest at the top, newest at the bottom:

```text
- YYYY-MM-DD | type | formula | first line | account
```

- `type`: `reel`, `carousel`, `story` or `comment`.
- `formula`: the hook formula as `#n` from `ig-reel/hooks.json`, or `-` when
  none was used.
- `first line`: the hook or opening line as the user approved it, with any `|`
  written as `/`.
- `account`: the handle it went out on; for a comment, the account commented
  on.

Read a line by splitting on ` | `. Lines that do not have this shape are older
notes: keep them, do not rewrite them.
<!-- /shared:log-schema -->

## Example

```text
- 2026-11-03 | reel | #4 | Nobody tells you this about pricing | @yourhandle
- 2026-11-03 | comment | - | The second slide is the whole argument | @someoneelse
```
