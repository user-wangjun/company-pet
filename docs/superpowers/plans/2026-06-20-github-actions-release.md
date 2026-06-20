# GitHub Actions Desktop Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a Windows x64 NSIS installer and an unsigned macOS Apple Silicon ARM64 DMG when a matching `v*` Git tag is pushed.

**Architecture:** Add one tag-triggered GitHub Actions workflow with independent Windows and macOS build jobs. Each job verifies the tag against all project version files and uploads its installer as a workflow artifact; a final Ubuntu job creates or resumes a draft GitHub Release, uploads both installers, and publishes the release only after both uploads succeed.

**Tech Stack:** GitHub Actions, Node.js 22, Rust stable, Tauri 2, GitHub CLI, actionlint.

---

## File Structure

- Create `.github/workflows/release.yml`: owns tag validation, Windows and
  macOS builds, artifact transfer, and atomic draft-to-published release flow.
- Existing application, pet-package, and release-artifact files remain
  unchanged.

### Task 1: Add the tagged desktop release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/release.yml` with this complete content:

```yaml
name: Release desktop installers

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false

jobs:
  windows-x64:
    name: Build Windows x64 NSIS
    runs-on: windows-latest
    steps:
      - name: Check out tagged source
        uses: actions/checkout@v7

      - name: Set up Node.js
        uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm

      - name: Set up Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install dependencies
        run: npm ci

      - name: Verify tag matches project versions
        shell: bash
        run: |
          node <<'NODE'
          const fs = require("node:fs");
          const expected = process.env.GITHUB_REF_NAME.replace(/^v/, "");
          const packageVersion = require("./package.json").version;
          const tauriVersion = require("./src-tauri/tauri.conf.json").version;
          const cargoText = fs.readFileSync("src-tauri/Cargo.toml", "utf8");
          const cargoVersion = cargoText.match(
            /^\[package\][\s\S]*?^version\s*=\s*"([^"]+)"/m,
          )?.[1];
          const versions = {
            "package.json": packageVersion,
            "src-tauri/Cargo.toml": cargoVersion,
            "src-tauri/tauri.conf.json": tauriVersion,
          };
          const mismatches = Object.entries(versions).filter(
            ([, version]) => version !== expected,
          );
          if (mismatches.length > 0) {
            console.error(`Tag ${process.env.GITHUB_REF_NAME} expects version ${expected}.`);
            for (const [file, version] of mismatches) {
              console.error(`${file}: ${version ?? "missing"}`);
            }
            process.exit(1);
          }
          console.log(`Release version verified: ${expected}`);
          NODE

      - name: Build Windows installer
        run: npm run tauri -- build --bundles nsis

      - name: Upload Windows installer
        uses: actions/upload-artifact@v7
        with:
          name: release-windows-x64
          path: src-tauri/target/release/bundle/nsis/*.exe
          if-no-files-found: error
          retention-days: 7

  macos-arm64:
    name: Build macOS Apple Silicon DMG
    runs-on: macos-15
    steps:
      - name: Check out tagged source
        uses: actions/checkout@v7

      - name: Set up Node.js
        uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm

      - name: Set up Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: aarch64-apple-darwin

      - name: Install dependencies
        run: npm ci

      - name: Verify tag matches project versions
        shell: bash
        run: |
          node <<'NODE'
          const fs = require("node:fs");
          const expected = process.env.GITHUB_REF_NAME.replace(/^v/, "");
          const packageVersion = require("./package.json").version;
          const tauriVersion = require("./src-tauri/tauri.conf.json").version;
          const cargoText = fs.readFileSync("src-tauri/Cargo.toml", "utf8");
          const cargoVersion = cargoText.match(
            /^\[package\][\s\S]*?^version\s*=\s*"([^"]+)"/m,
          )?.[1];
          const versions = {
            "package.json": packageVersion,
            "src-tauri/Cargo.toml": cargoVersion,
            "src-tauri/tauri.conf.json": tauriVersion,
          };
          const mismatches = Object.entries(versions).filter(
            ([, version]) => version !== expected,
          );
          if (mismatches.length > 0) {
            console.error(`Tag ${process.env.GITHUB_REF_NAME} expects version ${expected}.`);
            for (const [file, version] of mismatches) {
              console.error(`${file}: ${version ?? "missing"}`);
            }
            process.exit(1);
          }
          console.log(`Release version verified: ${expected}`);
          NODE

      - name: Build macOS installer
        run: npm run tauri -- build --target aarch64-apple-darwin --bundles dmg

      - name: Upload macOS installer
        uses: actions/upload-artifact@v7
        with:
          name: release-macos-arm64
          path: src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/*.dmg
          if-no-files-found: error
          retention-days: 7

  publish-release:
    name: Publish GitHub Release
    runs-on: ubuntu-latest
    needs:
      - windows-x64
      - macos-arm64
    steps:
      - name: Download installers
        uses: actions/download-artifact@v8
        with:
          pattern: release-*
          path: release-assets
          merge-multiple: true

      - name: Verify release assets
        shell: bash
        run: |
          mapfile -t windows_assets < <(find release-assets -maxdepth 1 -type f -name '*.exe')
          mapfile -t macos_assets < <(find release-assets -maxdepth 1 -type f -name '*.dmg')
          if [[ ${#windows_assets[@]} -ne 1 || ${#macos_assets[@]} -ne 1 ]]; then
            echo "Expected exactly one Windows EXE and one macOS DMG."
            find release-assets -maxdepth 1 -type f -print
            exit 1
          fi

      - name: Create draft release if needed
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          draft_state="$(
            gh release view "$GITHUB_REF_NAME" --json isDraft --jq '.isDraft' 2>/dev/null || true
          )"
          if [[ -z "$draft_state" ]]; then
            gh release create "$GITHUB_REF_NAME" \
              --verify-tag \
              --draft \
              --title "愈心桌宠 $GITHUB_REF_NAME" \
              --notes "Preparing release assets."
          elif [[ "$draft_state" != "true" ]]; then
            echo "Release $GITHUB_REF_NAME already exists and is public."
            exit 1
          fi

      - name: Upload installers and publish release
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          cat > release-notes.md <<'NOTES'
          ## 安装包

          - Windows x64：下载 `.exe` 安装包。
          - macOS Apple Silicon：下载 `.dmg`，支持 M1、M2、M3、M4 及后续 ARM64 Mac。

          > macOS 安装包目前未签名、未公证。首次打开可能需要前往“系统设置 → 隐私与安全”并选择“仍要打开”。不支持 Intel Mac。
          NOTES

          gh release upload "$GITHUB_REF_NAME" release-assets/* --clobber
          gh release edit "$GITHUB_REF_NAME" \
            --title "愈心桌宠 $GITHUB_REF_NAME" \
            --notes-file release-notes.md \
            --draft=false \
            --latest
```

- [ ] **Step 2: Run actionlint to validate GitHub Actions syntax and expressions**

Download and run actionlint v1.7.12 without adding it to the repository:

```powershell
$temp = Join-Path $env:TEMP "actionlint-1.7.12"
New-Item -ItemType Directory -Force $temp | Out-Null
gh release download v1.7.12 `
  --repo rhysd/actionlint `
  --pattern "actionlint_1.7.12_windows_x86_64.zip" `
  --dir $temp `
  --clobber
Expand-Archive `
  -Path (Join-Path $temp "actionlint_1.7.12_windows_x86_64.zip") `
  -DestinationPath $temp `
  -Force
& (Join-Path $temp "actionlint.exe") ".github/workflows/release.yml"
```

Expected: exit code `0` and no diagnostics.

- [ ] **Step 3: Confirm the workflow contains the agreed release contract**

Run:

```powershell
rg -n 'tags:|"v\\*"|windows-x64|macos-arm64|aarch64-apple-darwin|--bundles nsis|--bundles dmg|--draft=false|Open Anyway|仍要打开' .github/workflows/release.yml
```

Expected: matches for the tag trigger, both platforms, both bundle commands,
draft publication, and unsigned macOS warning.

- [ ] **Step 4: Commit the workflow**

```powershell
git add -- .github/workflows/release.yml
git diff --cached --check
git commit -m "ci: publish tagged desktop installers"
```

Expected: one commit containing only `.github/workflows/release.yml`.

### Task 2: Verify the repository and hand off the first tag

**Files:**
- Verify: `.github/workflows/release.yml`
- Verify unchanged: `package.json`
- Verify unchanged: `src-tauri/Cargo.toml`
- Verify unchanged: `src-tauri/tauri.conf.json`

- [ ] **Step 1: Run the full frontend test suite**

Run:

```powershell
npm test
```

Expected: all Vitest suites pass with zero failures.

- [ ] **Step 2: Run the frontend production build**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite complete with exit code `0`.

- [ ] **Step 3: Run Rust tests**

Run:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: all Rust tests pass with zero failures.

- [ ] **Step 4: Run the Rust compile check**

Run:

```powershell
cargo check --manifest-path src-tauri/Cargo.toml
```

Expected: exit code `0`.

- [ ] **Step 5: Inspect scope and history**

Run:

```powershell
git status --short --branch
git show --stat --oneline HEAD
git diff HEAD~1 -- .github/workflows/release.yml
```

Expected:

- The implementation commit contains only `.github/workflows/release.yml`.
- Existing unrelated untracked pet QA files remain untracked and untouched.
- The branch remains ahead of `origin/main`; nothing is pushed automatically.

- [ ] **Step 6: Hand off the first release command**

After the workflow commit is pushed to GitHub and the three version files are
updated to the intended release version, create the matching tag:

```powershell
git tag v0.1.4
git push origin main
git push origin v0.1.4
```

Expected: GitHub Actions runs `Release desktop installers`; it publishes the
Release only after both platform installers build and upload successfully.
