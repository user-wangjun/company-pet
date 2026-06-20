# GitHub Actions Release Design

## Goal

Publish installable desktop builds automatically when a version tag matching
`v*` is pushed to GitHub.

Each tagged release will contain:

- A Windows x64 NSIS installer.
- A macOS Apple Silicon ARM64 DMG.

The macOS build will be unsigned and unnotarized because the project does not
currently have an Apple Developer Program account or Developer ID certificate.

## Scope

The implementation will add one GitHub Actions workflow under
`.github/workflows/`. It will not change application behavior, pet packages,
or existing release artifacts.

The macOS artifact will support Macs with Apple Silicon processors, including
the M1, M2, M3, M4, and later compatible ARM64 generations. It will not support
Intel Macs.

## Trigger and Version Contract

The workflow will run when a tag matching `v*` is pushed, for example:

```text
v0.1.4
```

Before building, the workflow will verify that the tag version matches the
versions in:

- `package.json`
- `src-tauri/Cargo.toml`
- `src-tauri/tauri.conf.json`

This prevents a tag such as `v0.1.4` from publishing binaries that still
identify themselves as version `0.1.3`.

## Workflow Architecture

The workflow will use two platform build jobs:

1. `windows-x64`
   - Runner: `windows-latest`
   - Rust target: the runner's native x64 Windows target
   - Bundle: NSIS installer

2. `macos-arm64`
   - Runner: `macos-latest`
   - Rust target: `aarch64-apple-darwin`
   - Bundle: DMG

Both jobs will:

- Check out the tagged source.
- Install the repository's locked Node.js dependencies with `npm ci`.
- Install a stable Rust toolchain and the required target.
- Validate the tag and project versions.
- Run the relevant Tauri production build.
- Upload the generated installer as a workflow artifact.

A final release job will run only after both builds succeed. It will download
the workflow artifacts, create the GitHub Release for the pushed tag, and
attach both installers. This avoids publishing a partially successful release.

The workflow will receive only the GitHub permission needed to publish release
assets:

```yaml
permissions:
  contents: write
```

## macOS Gatekeeper Behavior

The DMG will not be code-signed or notarized. macOS may block the first launch.
Users can allow it from:

```text
System Settings → Privacy & Security → Open Anyway
```

Release notes will identify the DMG as an unsigned Apple Silicon test build.
Managed Macs may prohibit users from bypassing Gatekeeper.

The workflow will keep signing concerns isolated so Apple signing and
notarization secrets can be added later without changing the build targets or
release trigger.

## Failure Handling

- A version mismatch will stop the workflow before compilation.
- Failure of either platform build will prevent creation of the GitHub Release.
- Build artifacts will remain visible in the failed workflow run where
  available, but no partial public release will be published.
- Re-running a failed workflow will rebuild both platform outputs from the same
  immutable tag.

## Verification

Local verification will cover:

- Existing JavaScript and TypeScript tests.
- Frontend production build.
- Rust tests and checks on the current Windows environment.
- YAML syntax and structural validation for the workflow.
- Inspection that only the intended workflow and documentation files changed.

The macOS DMG itself can only be fully verified by running the GitHub Actions
workflow on a `macos-latest` runner. The first real tagged run will therefore be
the platform integration test.

## Release Procedure

For each release:

1. Update all three project version files to the same version.
2. Commit and push the release changes.
3. Create and push the matching tag, for example:

   ```bash
   git tag v0.1.4
   git push origin v0.1.4
   ```

4. GitHub Actions builds both installers and publishes the GitHub Release.
