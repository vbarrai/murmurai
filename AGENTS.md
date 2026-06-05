# AGENTS.md

Guidance for AI agents working in the murmurai repository.

## Release

murmurai uses a **fully automated, tag-driven release process**. A release is
produced entirely by GitHub Actions; there are no manual build or upload steps.

### How it works

- Versioning is **dynamic**, derived from git tags via `setuptools_scm`
  (`pyproject.toml` → `[tool.setuptools_scm]`). The version is **never** edited
  by hand in source files.
- Pushing a tag matching `v*` triggers `.github/workflows/release.yml`, which:
  1. Builds the `.app` with PyInstaller (`murmurai.spec`).
  2. Packages it into a DMG (`create-dmg`).
  3. Creates a GitHub Release with auto-generated notes and the DMG attached.
  4. Updates the Homebrew cask (`vbarrai/homebrew-tap`, `Casks/murmurai.rb`)
     with the new version and DMG SHA256.
- The workflow itself patches `CFBundleVersion` / `CFBundleShortVersionString`
  in `murmurai.spec` and `version` in `pyproject.toml` at build time from the
  tag. Do not commit version numbers into those files.

### Versioning policy

- Semantic versioning, `vMAJOR.MINOR.PATCH`.
- Pre-1.0: new features → bump **minor**; bug fixes only → bump **patch**.

### Procedure for cutting a release

1. Ensure you are on `main`, the working tree is clean, and `main` is pushed
   and up to date with the remote.
2. Determine the next version from the commits since the last tag
   (`git log $(git describe --tags --abbrev=0)..HEAD --oneline`).
3. Confirm the exact version with the user before tagging.
4. Create and push an **annotated** tag — this is the only action that ships:
   ```sh
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
5. The release workflow does the rest. Verify it succeeds:
   ```sh
   gh run watch
   gh release view vX.Y.Z
   ```

### Guardrails

- **Never** push a tag without explicit user confirmation of the version — the
  tag push is irreversible (it triggers a public release and Homebrew update).
- Do not manually edit version strings in `pyproject.toml` or `murmurai.spec`.
- Do not create the GitHub Release or DMG by hand; let the workflow do it.
