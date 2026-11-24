# Learnings — skill-creator

- `skill-creator` itself must keep its own `LEARNINGS.md` and `EVALS.md`; otherwise the self-improvement rule points to missing files and cannot be followed reliably (2026-05-13, audit before adding supporting files to workflow skills).
- Preserve the Claude-oriented install target (`.claude/skills/`) even when local working copies such as `.agents/skills/` exist; adapter paths are not the source-of-truth target (2026-05-13, user correction during skill-creator improvement).
