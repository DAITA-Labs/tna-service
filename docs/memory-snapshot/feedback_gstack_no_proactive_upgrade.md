---
name: Don't auto-upgrade gstack mid-skill
description: User has gstack installed and doesn't want me to spend cycles upgrading it or peeking at its setup script during unrelated workflows
type: feedback
originSessionId: b9582e52-0132-4ae2-a2d2-53fb7a19a63c
---
When the gstack preamble surfaces `UPGRADE_AVAILABLE`, do NOT proactively
run the inline upgrade flow or read `setup`/install internals unless the
upgrade is genuinely blocking the current task. The user already has gstack
installed and views these side-quests as friction.

**Why:** During /setup-gbrain on 2026-05-06 I started peeking at
`~/.claude/skills/gstack/setup` and the user interrupted with "i already
have gstack skill" — i.e. stop fiddling with the install, just run the
skill they invoked.

**How to apply:** If the preamble shows `UPGRADE_AVAILABLE`, mention it in
one line, treat it as informational, and continue with the actual skill
workflow. Only invoke `/gstack-upgrade` if (a) the user asks, or (b) a
helper script in the skill literally fails because of the version gap and
upgrading is the only fix.
