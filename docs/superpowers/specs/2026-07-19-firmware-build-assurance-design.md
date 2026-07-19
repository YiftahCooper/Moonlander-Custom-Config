# Firmware Build Assurance Design

## Goal

Make every published Moonlander firmware release fail closed, traceable to its exact inputs, reproducible enough to diagnose, and protected from accidental replacement. A green cloud build will mean **CI-verified firmware candidate**; only a successful physical flash and reconnect can mean **hardware-accepted firmware**.

## Scope

In scope:

- Remove the invalid `qmk_firmware` gitlink that produces checkout cleanup errors.
- Validate workflow inputs and Oryx responses before modifying the workspace.
- Run the repository's firmware patch tests in Actions.
- Prove the patcher is idempotent against the downloaded Oryx source.
- Resolve the exact ZSA QMK branch and commit and fail if Oryx's branch is unavailable.
- Use a dated build image, record toolchain versions, and pin JavaScript actions to immutable commit SHAs.
- Require a closed firmware output inventory and generate a SHA-256 manifest.
- Publish uniquely named, non-overwriting releases containing the firmware, checksum, and manifest.
- Verify the published release inventory before declaring the workflow successful.

Out of scope:

- Automatically flashing Yiftah's active keyboard from GitHub Actions.
- Requiring a permanently attached spare Moonlander or self-hosted runner.
- Signing firmware with a private code-signing key; byte identity and provenance are sufficient for this personal repository.
- Changing tap dances, RGB behavior, CopyQ commands, or Windhawk behavior.
- Redesigning the Oryx snapshot synchronization mechanism beyond removing the broken gitlink and preserving clear stage failures.

## Current Evidence

- Run `29696218074` linked an ELF, generated `zsa_moonlander_reva_3aMQz.bin`, and reported a 57,172-byte firmware image.
- The same run uploaded and released the binary successfully.
- Checkout cleanup still emitted exit code 128 because Git tracks `qmk_firmware` with mode `160000` while `.gitmodules` is absent.
- The workflow silently falls back to QMK `master` when `firmware<qmkVersion>` is absent.
- `Dockerfile` uses floating `debian:latest` and unpinned Python packages.
- Release identity includes the Oryx revision but not the custom-source or QMK commit, so a later custom-code build can overwrite an older release for the same Oryx revision.

## Architecture

The existing single workflow remains the entry point. It is hardened as a sequence of explicit gates:

```text
validated inputs
  -> validated Oryx response and source archive
  -> repository tests
  -> patched-source invariants and idempotence
  -> exact ZSA QMK commit
  -> clean compile
  -> closed artifact inventory
  -> firmware manifest and SHA-256
  -> Actions artifact
  -> non-overwriting GitHub release
  -> published-asset verification
  -> Oryx snapshot synchronization
```

`scripts/firmware_release.py` owns pure validation, output-name selection, hashing, and manifest generation. The workflow owns external operations such as downloading Oryx, cloning QMK, compiling, uploading, and publishing. This keeps policy testable without emulating GitHub Actions.

## Release Identity

Each candidate is identified by:

- repository commit (`github.sha`);
- Oryx layout ID and revision hash;
- geometry;
- Oryx QMK version;
- exact ZSA QMK commit;
- firmware filename, byte length, and SHA-256;
- compiler, Python, and container-base identities.

The release tag includes the geometry, layout ID, Oryx hash, twelve characters of the repository commit, and twelve characters of the QMK commit. `overwrite_files` is disabled. Re-running the exact same inputs may verify and reuse the same release only after its assets match the manifest; changed inputs always produce a new release.

## Failure and Recovery Contract

| Stage | Success receipt | Partial state | Safe retry | Rollback |
| --- | --- | --- | --- | --- |
| Oryx download | Valid ZIP plus revision metadata | `source.zip`/temporary extraction only | Rerun download | None |
| Patch | Tests pass and second patch is byte-identical | Temporary patched directory | Rerun patch from clean downloaded source | None |
| QMK resolution | Exact branch and commit recorded | Temporary clone | Rerun clone | None |
| Build | One non-empty expected firmware plus ELF | Runner-local build directory | Rerun build | None |
| Package | Manifest and checksum match firmware bytes | Runner-local `dist/` | Regenerate package | None |
| Artifact upload | GitHub artifact URL/digest | Expiring Actions artifact | Retry upload from verified `dist/` in the same run | None |
| Release publication | Unique release with exact three-asset inventory | Draft/incomplete release | Delete only the incomplete candidate or retry its missing assets | Preserve all prior releases |
| Snapshot sync | Clean layout-only commit or verified no-op | Unpushed runner commit | Retry sync against current `main` | Release remains identifiable; prior snapshots preserved |

## Acceptance Criteria

### AC-001: Invalid or incomplete Oryx input cannot reach the patcher

- Invalid layout IDs, unsupported geometry, HTTP failures, GraphQL errors, missing revision hashes, non-numeric QMK versions, invalid ZIP files, and missing `keymap.c` stop the run.
- Verification: unit tests for input parsing plus a workflow contract test and one successful live workflow.

### AC-002: Patch regressions fail before compilation

- The Python firmware tests run before QMK cloning.
- Running the patcher twice on the downloaded source leaves the patched files byte-identical.
- Verification: red-first unit/contract tests and workflow logs.

### AC-003: QMK compatibility fails closed

- The workflow checks out `firmware<qmkVersion>` at an exact commit.
- A missing branch fails the run; `master` is never substituted.
- The exact QMK commit is present in the manifest and release identity.
- Verification: workflow helper tests with present/missing branch fixtures and live logs.

### AC-004: Firmware selection is unambiguous

- A fresh build must produce exactly one expected `.bin` or `.hex` candidate and its corresponding ELF.
- Moonlander geometries require `.bin`.
- Empty files, unexpected extensions, multiple candidates, or missing ELF files fail the run.
- Verification: unit tests over temporary artifact inventories and live build logs.

### AC-005: Published bytes are attributable and immutable by convention

- The manifest SHA-256 and byte length match the published firmware.
- The release contains exactly the firmware, `<firmware>.sha256`, and `<firmware>.manifest.json`.
- The release tag includes Oryx, repository, and QMK identities, and publishing does not overwrite files.
- Verification: unit tests, post-publication GitHub API comparison, and downloaded checksum verification.

### AC-006: Workflow success has no concealed Git checkout failure

- `qmk_firmware` is no longer a gitlink, the workflow clones QMK outside the repository checkout, and checkout cleanup completes without the existing exit-128 warning.
- Verification: `git ls-files --stage qmk_firmware` returns no mode-160000 entry and a live workflow has clean post-checkout logs.

### AC-007: Claims stop at the proven layer

- A successful workflow labels the release as `CI-verified; physical flash not yet witnessed`.
- A physical Keymapp/Zapp flash and keyboard reconnect remain the manual hardware-acceptance gate.
- Verification: release body inspection plus manual flash receipt when Yiftah chooses to accept a candidate.

