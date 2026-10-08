# Domain Docs

How the engineering skills (`grill-with-docs`, `domain-modeling`, `to-spec`, `to-tickets`,
`triage`, …) consume this repo's domain documentation.

Single-context repo. **The glossary is `GLOSSARY.md`** at the repo root; this repo has no
`CONTEXT.md`. Wherever a skill says `CONTEXT.md`, read and write `GLOSSARY.md` instead, in its
existing format (one `## Term` heading per term, a short definition, the source). Decisions
live in `docs/adr/NNNN-slug.md` (created when the first ADR is needed).

## Before exploring, read these

- `GLOSSARY.md` — the project vocabulary.
- `docs/adr/` — ADRs that touch the area you're about to work in.
- Production rules are not glossary terms: they live in `docs/domain/` with citations, and
  open conflicts between sources in `docs/domain/conflicts.md` (see `AGENTS.md`).

If `docs/adr/` doesn't exist, proceed silently.

## Use the glossary's vocabulary

When your output names a domain concept (issue title, proposal, test name), use the term as
defined in `GLOSSARY.md`. A missing term is a signal: either you are inventing language, or
there is a real gap — add it via `domain-modeling`.

## Flag ADR conflicts

If your output contradicts an existing ADR, say so explicitly instead of overriding it:

> _Contradicts ADR-0007 (…), but worth reopening because…_
