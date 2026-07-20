# Firmware Build Assurance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Oryx-to-Moonlander workflow into a fail-closed, provenance-rich firmware release pipeline while clearly separating CI verification from physical flash acceptance.

**Architecture:** Keep the existing manual workflow entry point, but move deterministic validation and manifest creation into a tested Python helper. Build from a fresh temporary ZSA QMK checkout at an exact commit, validate a closed output inventory, publish uniquely identified non-overwriting assets, and verify the published release before success.

**Tech Stack:** GitHub Actions, Bash, Python 3 standard library, Docker, ZSA QMK, `unittest`, GitHub Releases.

## Global Constraints

- Preserve Oryx layout ID `3aMQz` and Moonlander `reva` as the defaults.
- Preserve all existing firmware behavior; this plan changes build and publication only.
- A missing Oryx revision, QMK branch, required patched invariant, firmware output, manifest field, or release asset fails closed.
- Never fall back from Oryx's `firmware<qmkVersion>` branch to QMK `master`.
- Never overwrite an earlier firmware asset.
- Preserve every prior release as rollback material.
- A green workflow proves a CI-verified candidate, not a witnessed physical flash.
- Pin GitHub Actions to full commit SHAs: checkout v6 `df4cb1c069e1874edd31b4311f1884172cec0e10`, upload-artifact v7 `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, action-gh-release v3 `c12583777ecdfd3be55c69cf75464299dc01057e` (verified at implementation time on 2026-07-20).
- Use `debian:bookworm-20260713-slim` as the dated build base; record its resolved image digest in every manifest.

---

### Task 1: Remove the invalid QMK gitlink and lock the workflow contract

**Files:**
- Modify: `.gitignore`
- Modify: `.github/workflows/fetch-and-build-layout.yml`
- Create: `tests/test_firmware_workflow.py`
- Remove from Git index: `qmk_firmware`

**Interfaces:**
- Produces: repository invariant `qmk_firmware` is an ignored runtime directory, never mode `160000`.
- Consumes: existing workflow path `.github/workflows/fetch-and-build-layout.yml`.

- [ ] **Step 1: Write failing repository-contract tests**

Add tests that read the workflow and `.gitignore`, then assert:

```python
def test_qmk_checkout_is_not_a_repository_gitlink(self):
    staged = subprocess.run(
        [GIT, "ls-files", "--stage", "qmk_firmware"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    self.assertNotRegex(staged, r"^160000 ")

def test_qmk_runtime_clone_is_ignored_and_uses_runner_temp(self):
    self.assertIn("/qmk_firmware/", GITIGNORE.read_text(encoding="utf-8"))
    self.assertIn('QMK_DIR="${RUNNER_TEMP}/qmk_firmware"', self.workflow)
```

- [ ] **Step 2: Run the focused test and verify RED**

```powershell
python -m unittest tests.test_firmware_workflow.FirmwareWorkflowContractTests -v
```

Expected: failures because `qmk_firmware` is still mode `160000`, is not ignored, and is cloned inside the checkout.

- [ ] **Step 3: Remove only the gitlink and ignore runtime clones**

```powershell
& 'C:\Program Files\Git\cmd\git.exe' rm --cached qmk_firmware
```

Append this exact entry to `.gitignore`:

```gitignore

# Runtime-only ZSA QMK checkout used by local/CI builds
/qmk_firmware/
```

Change the workflow to export `QMK_DIR=${RUNNER_TEMP}/qmk_firmware` through `$GITHUB_ENV`; all later QMK paths must consume `$QMK_DIR`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: all contract tests pass.

- [ ] **Step 5: Commit the isolated cleanup**

```powershell
git add .gitignore .github/workflows/fetch-and-build-layout.yml tests/test_firmware_workflow.py
git commit -m "Remove invalid QMK gitlink"
```

### Task 2: Validate workflow inputs and Oryx responses before patching

**Files:**
- Create: `scripts/firmware_release.py`
- Create: `tests/test_firmware_release.py`
- Modify: `.github/workflows/fetch-and-build-layout.yml`

**Interfaces:**
- Produces: `validate_layout_id(value: str) -> str`.
- Produces: `validate_geometry(value: str) -> str`.
- Produces CLI `python scripts/firmware_release.py validate-inputs --layout-id ID --geometry GEOMETRY`.
- Consumes: workflow-dispatch `layout_id` and `layout_geometry`.

- [ ] **Step 1: Write failing pure validation tests**

Cover accepted `3aMQz` and `moonlander/reva`, rejected whitespace/shell metacharacters/path separators in layout IDs, and geometry values outside the workflow's declared list.

```python
self.assertEqual(validate_layout_id("3aMQz"), "3aMQz")
with self.assertRaises(ValueError):
    validate_layout_id("3aMQz;echo bad")
with self.assertRaises(ValueError):
    validate_geometry("moonlander/unknown")
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m unittest tests.test_firmware_release -v
```

Expected: import failure because `scripts/firmware_release.py` does not exist.

- [ ] **Step 3: Implement standard-library validation**

Use `re.fullmatch(r"[A-Za-z0-9_-]+", value)` for layout IDs and an explicit immutable set matching the workflow geometry choices. The CLI returns exit code `2` with a bounded message for invalid input.

- [ ] **Step 4: Harden Oryx network and schema handling**

Pass GitHub inputs through `env`, never interpolate them directly into shell programs. Use:

```bash
curl --fail-with-body --silent --show-error --location \
  --retry 3 --retry-all-errors \
  'https://oryx.zsa.io/graphql' \
  --header 'Content-Type: application/json' \
  --data "${graphql_request}" > response.json

jq -e '.data.layout.revision.hashId | strings | select(length > 0)' response.json
jq -e '.data.layout.revision.qmkVersion | numbers' response.json
```

Download the source with the same retry/failure flags, require `unzip -t` success, extract into a fresh directory, and require `keymap.c`, `config.h`, and `rules.mk` before patching.

- [ ] **Step 5: Run focused and full tests**

```powershell
python -m unittest tests.test_firmware_release tests.test_firmware_workflow -v
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/firmware_release.py tests/test_firmware_release.py .github/workflows/fetch-and-build-layout.yml
git commit -m "Validate Oryx firmware inputs"
```

### Task 3: Gate compilation on tests and real-source patch idempotence

**Files:**
- Modify: `.github/workflows/fetch-and-build-layout.yml`
- Modify: `tests/test_firmware_workflow.py`

**Interfaces:**
- Produces: source-test receipt from `python -m unittest discover -s tests -v`.
- Produces: actual-download idempotence receipt containing the before/after SHA-256 of all patched files.

- [ ] **Step 1: Add failing workflow-contract assertions**

Require the unit-test step to precede QMK cloning and require two patcher invocations separated by a deterministic tree digest comparison.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest tests.test_firmware_workflow -v
```

Expected: failures because the workflow does not run the full suite or patch the downloaded source twice.

- [ ] **Step 3: Add source and idempotence gates**

Before downloading QMK, run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/patch_keymap.py scripts/firmware_release.py
```

After the first patch, hash the complete patched layout inventory with sorted paths, run the patcher again, hash it again, and require identical digests:

```bash
first_digest="$(find oryx_source -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"
python3 scripts/patch_keymap.py oryx_source
second_digest="$(find oryx_source -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"
test "${first_digest}" = "${second_digest}"
```

- [ ] **Step 4: Verify GREEN and commit**

Run the focused and full Python suites, then:

```powershell
git add .github/workflows/fetch-and-build-layout.yml tests/test_firmware_workflow.py
git commit -m "Gate firmware build on patch tests"
```

### Task 4: Resolve an exact compatible ZSA QMK commit and dated toolchain

**Files:**
- Modify: `.github/workflows/fetch-and-build-layout.yml`
- Modify: `Dockerfile`
- Modify: `tests/test_firmware_workflow.py`

**Interfaces:**
- Produces workflow outputs `qmk_branch`, `qmk_commit`, `container_base`, `compiler_version`, and `python_version`.
- Consumes Oryx `firmware_version`.

- [ ] **Step 1: Add failing fail-closed contract tests**

Assert the workflow contains no `git checkout master`, no `defaulting to master`, checks `refs/remotes/origin/firmware${firmware_version}`, checks out a detached resolved SHA, and records it in `$GITHUB_OUTPUT`.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest tests.test_firmware_workflow -v
```

Expected: failure against the current fallback.

- [ ] **Step 3: Implement exact QMK resolution**

Clone into a fresh `$RUNNER_TEMP/qmk_firmware`, fetch only the required branch, and fail when it is absent:

```bash
qmk_branch="firmware${FIRMWARE_VERSION}"
git init "${QMK_DIR}"
git -C "${QMK_DIR}" remote add origin https://github.com/zsa/qmk_firmware.git
git -C "${QMK_DIR}" fetch --depth 1 origin "refs/heads/${qmk_branch}:refs/remotes/origin/${qmk_branch}"
qmk_commit="$(git -C "${QMK_DIR}" rev-parse "refs/remotes/origin/${qmk_branch}^{commit}")"
git -C "${QMK_DIR}" checkout --detach "${qmk_commit}"
git -C "${QMK_DIR}" submodule update --init --recursive
```

Any fetch/ref-resolution failure stops the job. Emit the branch and full commit as step outputs.

- [ ] **Step 4: Stabilize and identify the build image**

Change the Docker base to:

```dockerfile
FROM debian:bookworm-20260713-slim
```

During implementation, resolve the pulled image's immutable `RepoDigest` after `docker pull`, record it as `container_base`, and make the build fail if no digest is available. Pin the installed `qmk` and `appdirs` Python package versions to the versions proven by the first successful candidate build. Print and record `arm-none-eabi-gcc --version` and `python3 --version`.

- [ ] **Step 5: Verify and commit**

```powershell
python -m unittest tests.test_firmware_workflow -v
git diff --check
git add Dockerfile .github/workflows/fetch-and-build-layout.yml tests/test_firmware_workflow.py
git commit -m "Pin QMK firmware build inputs"
```

### Task 5: Validate a closed firmware inventory and generate the manifest

**Files:**
- Modify: `scripts/firmware_release.py`
- Modify: `tests/test_firmware_release.py`
- Modify: `.github/workflows/fetch-and-build-layout.yml`

**Interfaces:**
- Produces: `select_firmware(candidates: list[Path], geometry: str, layout_id: str) -> Path`.
- Produces: `write_manifest(path: Path, metadata: Mapping[str, object]) -> None`.
- Produces: `dist/<firmware>`, `dist/<firmware>.sha256`, `dist/<firmware>.manifest.json`.

- [ ] **Step 1: Write failing artifact tests**

Cover zero candidates, multiple candidates, empty files, Moonlander `.hex`, wrong layout/geometry filename, one valid `.bin`, stable JSON ordering, byte length, and SHA-256.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest tests.test_firmware_release -v
```

- [ ] **Step 3: Implement closed selection and canonical manifest output**

Require exactly one candidate from a freshly cleaned QMK root. For Moonlander, require a `.bin`; require the matching `.elf` below `.build`. Copy only the selected firmware into a new `dist/` directory. Write JSON with `sort_keys=True`, UTF-8, and a trailing newline. The manifest contains:

```json
{
  "artifact": {"filename": "zsa_moonlander_reva_3aMQz.bin", "sha256": "...", "size_bytes": 57172},
  "build": {"compiler": "...", "container_base": "...", "python": "..."},
  "oryx": {"geometry": "moonlander/reva", "layout_id": "3aMQz", "qmk_version": 24, "revision": "..."},
  "source": {"repository": "YiftahCooper/Moonlander-Custom-Config", "commit": "..."},
  "zsa_qmk": {"branch": "firmware24", "commit": "..."},
  "verification": {"hardware_flash_witnessed": false, "level": "ci-verified-candidate"}
}
```

The checksum file uses the portable format `<sha256>  <filename>\n`.

- [ ] **Step 4: Record ELF size evidence**

Run `arm-none-eabi-size` against the ELF and save its output in the Actions log. QMK/linker failure remains authoritative for capacity; do not introduce an arbitrary hand-maintained byte ceiling.

- [ ] **Step 5: Verify and commit**

```powershell
python -m unittest tests.test_firmware_release -v
python -m unittest discover -s tests -v
git add scripts/firmware_release.py tests/test_firmware_release.py .github/workflows/fetch-and-build-layout.yml
git commit -m "Add firmware provenance manifest"
```

### Task 6: Publish an immutable-by-identity release and verify it

**Files:**
- Modify: `.github/workflows/fetch-and-build-layout.yml`
- Modify: `tests/test_firmware_workflow.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: verified `dist/` and manifest metadata from Task 5.
- Produces: one Actions artifact and one uniquely tagged GitHub release with an exact three-file inventory.

- [ ] **Step 1: Add failing publication-contract tests**

Require full action SHAs from Global Constraints, `if-no-files-found: error`, `overwrite_files: false`, three release assets, `target_commitish: ${{ github.sha }}`, a tag containing short source and QMK SHAs, and a post-release verification step.

- [ ] **Step 2: Verify RED**

```powershell
python -m unittest tests.test_firmware_workflow -v
```

- [ ] **Step 3: Upgrade and pin actions**

Use exactly:

```yaml
- uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6
- uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
- uses: softprops/action-gh-release@c12583777ecdfd3be55c69cf75464299dc01057e # v3
```

Upload the complete `dist/` inventory with `if-no-files-found: error`.

- [ ] **Step 4: Construct a unique non-overwriting release**

Build the tag in Bash from validated fields:

```bash
source_short="${GITHUB_SHA:0:12}"
qmk_short="${QMK_COMMIT:0:12}"
release_tag="firmware-${NORMALIZED_GEOMETRY}-${LAYOUT_ID}-${ORYX_HASH}-${source_short}-${qmk_short}"
```

Set `overwrite_files: false`, `target_commitish: ${{ github.sha }}`, and publish exactly the firmware, checksum, and manifest. The release body must say `CI-verified candidate; physical flash not yet witnessed`.

- [ ] **Step 5: Verify the published release through GitHub's API**

Use `gh release view "$RELEASE_TAG" --json assets,tagName,targetCommitish` to require the expected tag, source commit, three names, and sizes. Download the three assets into a new temporary directory and run `sha256sum --check` there. Failure leaves prior releases untouched and marks this run failed at publication verification.

- [ ] **Step 6: Update documentation**

Document the three assurance levels:

```text
Build passed -> source compiled.
CI-verified candidate -> manifest, digest, inventory, and publication gates passed.
Hardware accepted -> Keymapp/Zapp flashed the file and the Moonlander reconnected successfully.
```

- [ ] **Step 7: Verify and commit**

```powershell
python -m unittest discover -s tests -v
git diff --check
git add .github/workflows/fetch-and-build-layout.yml tests/test_firmware_workflow.py README.md
git commit -m "Verify published firmware releases"
```

### Task 7: Run a live candidate and close the acceptance matrix

**Files:**
- Modify only if evidence requires correction: files changed in Tasks 1-6.
- Produce: GitHub Actions run, artifact URL, release URL, and verification notes.

**Interfaces:**
- Consumes: committed workflow hardening.
- Produces: source, package, and publication receipts; physical acceptance remains manual.

- [ ] **Step 1: Run all local verification fresh**

```powershell
python -m unittest discover -s tests -v
node --test host_tools/copyq/tests/*.test.js
dotnet test host_tools/reselect
python -m py_compile scripts/patch_keymap.py scripts/firmware_release.py
git diff --check
```

- [ ] **Step 2: Push the verified implementation to `main` and dispatch one workflow run**

Do not dispatch if push fails. Record the pushed commit and workflow run ID.

- [ ] **Step 3: Check every CI receipt**

Require:

- no checkout cleanup error or Node-20 warning;
- Python tests and actual-source idempotence pass;
- exact Oryx revision, QMK branch, QMK commit, container digest, and compiler are logged;
- exactly one firmware and one ELF are selected;
- manifest/checksum generation passes;
- Actions artifact upload passes;
- release publication and downloaded checksum verification pass;
- Oryx snapshot synchronization either makes a layout-only commit or reports a clean no-op.

- [ ] **Step 4: Preserve rollback and report the hardware boundary**

Keep the last known-good release. Do not delete or overwrite it. Report the new release as `CI-verified candidate` until Yiftah flashes it with Keymapp or Zapp, sees the flasher's successful validation, and confirms the Moonlander reconnects and types normally.

- [ ] **Step 5: Correct only the failed stage if necessary**

If the live run fails, preserve its logs and artifact, add a red-first regression at the failed boundary, change only the responsible task's files, rerun focused tests, and dispatch one corrected candidate. Do not repeat unrelated accepted work.
