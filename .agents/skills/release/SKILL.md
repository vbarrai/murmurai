---
name: release
description: >
  Prepare and publish a new release. Use this whenever the user wants to cut a
  release, ship a new version, tag a release, publish a package, or asks "what's in
  the next release" / "prepare a release" / "release vX.Y". It inspects commits since
  the last tag, checks the version is consistent with the tag to be created, drafts a
  clean changelog, shows the user exactly what will ship, asks for explicit
  permission, then runs the project's release procedure. Trigger it even if the user
  only says "let's release" or "ship it" without naming a version.
---

# Release

This skill drives the release process for any project. It is deliberately
**project-agnostic**: the *process* (verify → changelog → permission → execute) is
fixed, but the concrete commands, version source, tag format, and publish mechanism
differ per project and must be read from the project, not assumed.

## Step 0 — Required guard: read this project's release specifics

This skill is project-agnostic, so it **requires** the project to declare its release
specifics in a **`## Release`** section of an agent context markdown file at the repo
root. The canonical cross-tool file is **`AGENTS.md`**, but projects use other context
markdown depending on their agent — `CLAUDE.md`, `GEMINI.md`, or whatever this repo
uses. Read whichever such file(s) the repo has and locate the section first.

**Guard — stop if the section is missing.** If the repo has no agent context markdown
file, or none of them contains a `## Release` (or "Releasing"/"Publishing") section,
do **not** attempt to release, guess the procedure, or infer it from CI files. Stop
and tell the user, in substance:

> The `release` skill needs a `## Release` section in this project's agent context
> file — `AGENTS.md` (preferred), or another context markdown like `CLAUDE.md` /
> `GEMINI.md` — describing how this project releases, and I couldn't find one.
> Releasing is irreversible and conventions vary per project, so I won't guess.
> Please add a `## Release` section covering: what triggers a publish, the version
> source of truth and how to bump it, the pre-release check command, the tag format
> and target branch, and how the changelog/release notes are produced. Then re-run
> the release.

Offer to draft that section for them — read `references/release-section-example.md`
for a ready-to-fill template and a completed example, then inspect the project's CI
workflows, package manifest, and `git tag` history to fill in the placeholders. Only
**write it after they confirm**, and then still stop so they can review before
releasing. Do not proceed to step 1 until a `## Release` section exists.

**When the section is present**, read it and note for the rest of the run:

- **What triggers a publish** (push a tag? a CI button? a manual command?).
- **The version source of truth** and how it's bumped.
- **The pre-release check command** (the aggregate test/lint/build gate, if any).
- **The tag format**, target branch, and whether tags are annotated.
- **How the changelog / release notes are produced** (and whether a `CHANGELOG.md`
  file is maintained or notes live only on the platform release).

Existing tags (`git tag --sort=-creatordate | head`) can confirm the naming
convention, but they supplement the `## Release` section — they don't replace it.

## Step 1 — Verify the release content

Gather the facts:

```bash
git fetch --tags --quiet
LAST_TAG=$(git describe --tags --abbrev=0)
echo "Last tag: $LAST_TAG"
echo "--- commits since $LAST_TAG ---"
git log "$LAST_TAG"..HEAD --oneline
echo "--- working tree / branch ---"
git status --porcelain
git rev-parse --abbrev-ref HEAD
```

Also read the current version from the project's version source (from step 0).

Then reason and report to the user:

- **Target version & tag.** Derive the tag from the version source per the project's
  convention. If CI enforces tag == version (common), the version is whatever is
  already committed — do **not** invent one. If the version still equals the last
  tag's, it hasn't been bumped: stop and ask the user what bump they want (see
  "Bumping the version") before continuing.
- **Content.** Draft the curated changelog now (see "Changelog format") and show it.
  This same text becomes the release notes, so the user reviews the real notes here.
  Call out breaking changes or changed defaults explicitly.
- **Sanity flags.** Warn if: the working tree is dirty, you're not on the release
  branch, there are zero commits since the last tag (nothing to release), or the
  intended tag already exists (`git tag -l "<tag>"`).

Keep it short and scannable — the user is deciding whether to ship.

### Changelog format

Read the commit subjects (and PR numbers) since the last tag and group them by
Conventional-Commit type. Don't dump raw `git log` — rewrite each line into a
human-readable, present-tense bullet and keep any `(#NN)` PR reference so it links.
Omit empty sections:

```markdown
### Features
- Short, present-tense description of the capability (#NN)

### Fixes
- What was broken and is now fixed (#NN)

### ⚠️ Notable changes
- Breaking change or changed default, with a one-line "what users must know" (#NN)

**Full changelog**: <compare-url last_tag...new_tag, if the host supports it>
```

Map types: `feat` → Features; `fix` → Fixes; `perf`/`refactor` → Improvements;
fold `docs`/`test`/`chore`/`build`/`ci` into a single **Internal** section (or drop
if purely mechanical). Always surface breaking changes / changed defaults under
**⚠️ Notable changes**, even if duplicated above. For a GitHub remote, the compare
URL is `https://github.com/<owner>/<repo>/compare/<last_tag>...<new_tag>` — derive
`<owner>/<repo>` from `git remote get-url origin`.

## Step 2 — Ask permission

Stop and get an explicit go-ahead before changing anything. Show the exact tag you
intend to push and state that it publishes/releases (per step 0). Use AskUserQuestion
or a direct question; do not proceed until the user clearly confirms. If they want a
different version, handle the bump first.

## Step 3 — Execute

Run the project's release procedure as learned in step 0. The usual shape:

1. **Pre-release gate** — run the project's aggregate check locally first so a
   failure surfaces *before* the tag is pushed (a bad tag that fails CI has to be
   deleted and recreated). Skip only if the project has no such command.
2. **Bump** (if not already done) — see "Bumping the version".
3. **Tag & push** — create the tag in the project's format and push it (or run the
   project's publish command if releases aren't tag-triggered). Example for a
   tag-triggered project:
   ```bash
   git tag -a "<tag>" -m "<tag>"
   git push origin "<tag>"
   ```
4. **Watch** the release pipeline to completion (e.g. `gh run watch` for GitHub
   Actions) and confirm it succeeded.
5. **Curated changelog** — if the platform release was created with auto-generated
   notes, replace them with the changelog the user approved. For GitHub:
   ```bash
   gh release edit "<tag>" --notes-file /tmp/release-notes-<tag>.md
   ```
   If the project maintains a `CHANGELOG.md` file instead, update that file (committed
   before the tag) rather than editing platform notes.

Report the outcome and link the release.

## Bumping the version

Only if the version hasn't been bumped for this release yet. The bump must be
committed to the release branch **before** tagging if CI compares the tag against the
committed version. Pick the bump from the commit content using semver intent: new
user-facing capability → minor; bugfix-only → patch; breaking change → major (or
minor while pre-1.0, but flag it loudly). Use the project's bump command (e.g.
`pnpm version <level>`, `npm version`, `uv version`, `cargo set-version`), push the
bump commit, then return to step 1. If the user already has a target version, follow it.

## Notes

- A pushed tag / published package is the point of no return — never ship without the
  content review and explicit permission (steps 1–2).
- To undo a tag pushed by mistake **before** the publish completes:
  `git push --delete origin <tag> && git tag -d <tag>`. Once a package registry has
  published a version, that version is permanent — bump to a new patch instead.
- Don't modify the release pipeline as part of cutting a release; use the existing one.
