# Hebrew Base-Layer Colour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recolour only Oryx's base colour to the former indicator blue while Hebrew is active.

**Architecture:** The Python patcher detects the dominant non-black HSV triplet in generated layer 0 and injects it as a C contract. The custom QMK overlay uses that contract and the existing RAW HID language state to recolour exact matches before Caps Lock is rendered.

**Tech Stack:** Python 3, `unittest`, generated QMK C, Oryx RGB Matrix ledmap.

## Global Constraints

- English renders the unmodified Oryx base layer.
- Hebrew replaces only the dominant non-black base-layer colour with brightness-scaled `RGB {40, 140, 255}`.
- Manually assigned colours and every higher layer remain unchanged.
- The language key receives no firmware colour override.
- The patcher remains idempotent and fails rather than guessing an ambiguous base colour.

---

### Task 1: Detect and inject the Oryx base colour

**Files:**
- Modify: `tests/test_patch_keymap.py`
- Modify: `scripts/patch_keymap.py`

**Interfaces:**
- Produces: `_detect_base_layer_hsv(content: str) -> tuple[int, int, int]`
- Produces: `_inject_language_base_hsv(content: str, hsv: tuple[int, int, int]) -> tuple[str, bool]`

- [x] **Step 1: Add failing detection and injection tests**

Assert the current fixture detects `(83, 233, 240)`, excludes `{0,0,0}`, rejects tied dominant colours, and injects one canonical macro block.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m unittest tests.test_patch_keymap.LanguageRgbOverlayPatchTests -v
```

Expected: failure because the detection and injection functions do not exist.

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

Verify the generated hook is before the Caps Lock block, the legacy `custom_language_rgb_indicator()` call and prototype are absent, only exact base HSV matches are recoloured, the target is `RGB {40,140,255}`, and English/non-base layers return without changes.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
python -m unittest tests.test_patch_keymap.LanguageRgbOverlayPatchTests -v
```

Expected: failures against the current blue/red single-key implementation.

- [x] **Step 3: Implement the overlay and canonical patch migration**

Have the custom overlay loop through `ledmap[0]`, compare each original HSV triplet with the injected macros, scale `40/140/255` by `rgb_matrix_config.hsv.v`, and set only matching LEDs. Canonicalize prototypes and move the hook before Caps Lock.

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
