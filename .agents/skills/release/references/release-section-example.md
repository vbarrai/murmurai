# Example `## Release` section

When a project lacks a `## Release` section (the step-0 guard), use this as a starting
template. Copy it into the project's agent context markdown file — `AGENTS.md`
(preferred, cross-tool), or another context file the repo already uses such as
`CLAUDE.md` / `GEMINI.md` — then **replace every bracketed `[…]` placeholder** with
the project's real values — inspect the CI workflow, the package manifest, and
`git tag` to fill them in. Delete any line that doesn't apply. Keep it terse: it's a
fact sheet the skill reads, not prose.

The bullets map 1:1 to what step 0 needs ("what triggers a publish", "version source",
"pre-release gate", "tag format", "changelog"). Don't drop a bullet — if something
genuinely doesn't apply, say so explicitly (e.g. "No pre-release check command").

---

## Release

- **Trigger**: [what kicks off a publish — e.g. pushing a `v*` git tag triggers `.github/workflows/publish.yml`; or a manual `npm publish`; or a CI "Release" button].
- **CI pipeline** ([workflow file]): [ordered steps — e.g. verify tag == version → lint/typecheck/test → build → publish to registry → create platform release].
- **Version source of truth**: [where the version lives — e.g. `package.json` `version` / `pyproject.toml` / `Cargo.toml`]. Bump with [`pnpm version <level>` / `npm version` / `uv version` / `cargo set-version`] on [branch] **before** tagging [if CI compares tag against the committed version].
- **Tag format**: [`vX.Y.Z` annotated / `X.Y.Z`], pushed from [`main`].
- **Pre-release gate**: [the one aggregate check command, e.g. `pnpm ci` = lint + test + build] — run locally before tagging so failures surface before the tag is pushed. [Or: "No pre-release check command."]
- **Versioning**: semver[, pre-1.0 — flag breaking changes loudly even in a minor bump].
- **Changelog**: [where notes live — e.g. on the platform release only (no `CHANGELOG.md`); the skill overwrites auto-generated notes via `gh release edit --notes-file`. OR: a `CHANGELOG.md` file updated and committed before the tag].
- **Tag commands**: [`git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`]; undo before publish with [`git push --delete origin vX.Y.Z && git tag -d vX.Y.Z`] (a published registry version is permanent).

---

## Filled example (maconfai's own section, for reference)

This is what a completed section looks like in practice:

```markdown
## Release

- **Trigger**: pushing a `v*` git tag triggers `.github/workflows/publish.yml`. There is no manual publish step.
- **CI pipeline** (`publish.yml`): `preflight` fails if the tag (minus `v`) ≠ `package.json` version → lint/typecheck/test → `pnpm build` → `npm publish --access public` → `gh release create --generate-notes`.
- **Version source of truth**: `package.json` `version`. Bump with `pnpm version <major|minor|patch>` on `main` before tagging.
- **Tag format**: `vX.Y.Z` (annotated), pushed from `main`.
- **Pre-release gate**: `pnpm ci` (= check + test --run + build).
- **Versioning**: semver, pre-1.0 — flag breaking changes loudly even in a minor bump.
- **Changelog**: lives on the GitHub release only (no `CHANGELOG.md`); the skill overwrites CI's auto-generated notes via `gh release edit --notes-file`.
- **Tag commands**: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`; undo before publish with `git push --delete origin vX.Y.Z && git tag -d vX.Y.Z`.
```
