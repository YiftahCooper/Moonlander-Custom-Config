# Hebrew Base-Layer Colour Implementation Plan

> **Status (2026-07-21): Brown revision implemented locally.** The patcher now sources Hebrew from Layer 2's black MIDI melody keys, currently `HSV {12, 255, 255}`. Workflow run [`29808688464`](https://github.com/YiftahCooper/Moonlander-Custom-Config/actions/runs/29808688464) proved the complete build pipeline for the superseded turquoise revision; the brown revision still requires a new workflow run and physical flash acceptance.

> This is the completed implementation record; checked steps preserve the test-first sequence and acceptance evidence.

**Goal:** Recolour only Oryx's base colour to the brown used by Layer 2's black MIDI keys while Hebrew is active.

**Architecture:** The Python patcher detects the dominant non-black HSV triplet in generated Layer 0, reads the shared HSV triplet from the ten semantic Layer 2 black-MIDI-key LED positions, and injects both as a C contract. The custom QMK overlay uses the Layer 0 value as an exact-match filter and renders the MIDI-key value through Oryx's brightness-aware HSV conversion before Caps Lock is rendered.

**Tech Stack:** Python 3, `unittest`, generated QMK C, Oryx RGB Matrix ledmap.

## Global Constraints

- English renders the unmodified Oryx base layer.
- Hebrew replaces only the dominant non-black base-layer colour with the shared colour of Layer 2's black MIDI melody keys; the current layout value is `HSV {12, 255, 255}`.
- Manually assigned colours and every higher layer remain unchanged.
- The language key receives no firmware colour override.
- The patcher remains idempotent and fails rather than guessing an ambiguous base colour or accepting inconsistent/black MIDI source keys.

---

### Task 1: Detect and inject the Oryx base colour

**Files:**
- Modify: `tests/test_patch_keymap.py`
- Modify: `scripts/patch_keymap.py`

**Interfaces:**
- Produces: `_detect_dominant_layer_hsv(content: str, layer_index: int) -> tuple[int, int, int]`
- Produces: `_inject_language_hsv_contract(content: str, base_hsv: tuple[int, int, int], hebrew_hsv: tuple[int, int, int]) -> tuple[str, bool]`

- [x] **Step 1: Add failing detection and injection tests**

Assert the accepted fixture detects `(83, 233, 240)`, excludes `{0,0,0}`, rejects tied dominant colours, and injects one canonical macro block.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m unittest tests.test_patch_keymap.LanguageRgbOverlayPatchTests -v
```

Red-stage result recorded during implementation: failure because the detection and injection functions did not exist.

- [x] **Step 3: Implement the minimal parser and macro injector**

Parse the balanced initializer for `ledmap[0]`, count non-black `{h,s,v}` triplets with `Counter`, require one unique maximum, and inject:

```c
/* ORYX_LANG_BASE_COLOR_PATCH */
#define MOONLANDER_BASE_H 83
#define MOONLANDER_BASE_S 233
#define MOONLANDER_BASE_V 240
```

- [x] **Step 4: Run the focused tests and verify GREEN**

Run the focused command from Step 2 and require all tests to pass.

### Task 2: Replace the single-key indicator with the base-colour overlay

**Files:**
- Modify: `tests/test_patch_keymap.py`
- Modify: `custom_qmk/custom_code.c`
- Modify: `3aMQz/custom_code.c`
- Modify: `scripts/patch_keymap.py`
- Modify: `3aMQz/keymap.c`
- Modify: `README.md`

**Interfaces:**
- Produces: `void custom_language_rgb_overlay(void)`
- Consumes: `MOONLANDER_BASE_H`, `MOONLANDER_BASE_S`, `MOONLANDER_BASE_V`, `ledmap[0]`, `rawhid_state.status_led_control`

- [x] **Step 1: Add failing overlay and migration tests**

Verify the generated hook is before the Caps Lock block, the legacy `custom_language_rgb_indicator()` call and prototype are absent, only exact base HSV matches are recoloured, the replacement comes from the injected Hebrew HSV contract, and English/non-base layers return without changes.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m unittest tests.test_patch_keymap.LanguageRgbOverlayPatchTests -v
```

Red-stage result recorded during implementation: failures against the former blue/red single-key implementation.

- [x] **Step 3: Implement the overlay and canonical patch migration**

Have the custom overlay loop through `ledmap[0]`, compare each original HSV triplet with the injected base macros, render the injected Hebrew HSV through `hsv_to_rgb_with_value()`, and set only matching LEDs. Canonicalize prototypes and move the hook before Caps Lock.

- [x] **Step 4: Regenerate and verify idempotence**

Run the patcher twice on `3aMQz` and require the second pass to leave `keymap.c` byte-identical.

- [x] **Step 5: Run complete verification**

```powershell
python -m unittest discover -s tests -v
node --test host_tools/copyq/tests/*.test.js
dotnet test host_tools/reselect
python -m py_compile scripts/patch_keymap.py
git diff --check
```

Expected: every suite passes and the diff check is clean.

- [x] **Step 6: Commit to main**

Commit the specification, plan, tests, patcher, custom firmware source, generated snapshot, and README together after verification.

### Task 3: Source the Hebrew colour from Layer 2's black MIDI keys

**Files:**
- Modify: `tests/test_patch_keymap.py`
- Modify: `scripts/patch_keymap.py`
- Modify: `custom_qmk/custom_code.c`
- Modify: `3aMQz/custom_code.c`
- Modify: `3aMQz/keymap.c`
- Modify: `README.md`

**Interfaces:**
- Produces: `_detect_dominant_layer_hsv(content: str, layer_index: int) -> tuple[int, int, int]`
- Produces: `_detect_midi_accidental_hsv(content: str) -> tuple[int, int, int]`
- Produces: `MOONLANDER_HEBREW_H`, `MOONLANDER_HEBREW_S`, and `MOONLANDER_HEBREW_V`
- Consumes: Oryx `ledmap[2]`, the ten Moonlander accidental-key LED indices, and `hsv_to_rgb_with_value(HSV)`

- [x] **Step 1: Add failing semantic MIDI-colour detection tests**

Assert that the accepted generated snapshot detects the ten black MIDI keys as `(12, 255, 255)`, ignores unrelated Layer 2 colours, rejects inconsistent or all-black source keys, injects all six macros exactly once, uses `hsv_to_rgb_with_value()` in the overlay, and contains none of the former `LANGUAGE_HEBREW_BASE_R/G/B` constants.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m unittest tests.test_patch_keymap.LanguageRgbOverlayPatchTests -v
```

Red-stage result recorded during implementation: four focused tests failed because the semantic black-MIDI-key detector did not exist.

- [x] **Step 3: Implement the semantic detector and update the six-macro contract**

Parse Layer 2 using the common balanced ledmap parser, read the ten fixed accidental-key LED positions, require exactly one shared non-black colour, inject that value alongside the detected Layer 0 base HSV, and render it through `hsv_to_rgb_with_value()`.

- [x] **Step 4: Regenerate and prove idempotence**

Run `python scripts/patch_keymap.py 3aMQz` twice and require the second pass to leave the generated tree byte-identical.

- [x] **Step 5: Run complete verification**

```powershell
python -m unittest discover -s tests -v
python -m py_compile scripts/patch_keymap.py scripts/firmware_release.py
git diff --check
```

Expected: all tests pass, both Python files compile, and the diff is clean.
