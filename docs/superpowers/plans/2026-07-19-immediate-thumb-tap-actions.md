# Immediate Thumb Tap Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the Moonlander text-tool F-keys at their terminal tap count instead of waiting for QMK's tap-dance settlement timeout.

**Architecture:** `patch_keymap.py` will replace the three signature-detected `on_dance_<n>()` callbacks with guarded immediate actions. Per-dance flags suppress the later `finished` callback and are cleared by `reset`, so surplus taps are absorbed without producing another action.

**Tech Stack:** Python 3 patcher and `unittest`; generated QMK C tap-dance callbacks.

## Global Constraints

- Language emits `F22` once on its second press.
- Left and right space emit `F19` and `F13` once on their third press.
- Surplus taps in the same tap-dance window do nothing.
- Existing single, hold, Caps Lock, period-space, and language-switch behavior remains unchanged.
- Dance identification remains signature-based and patching remains idempotent and fail-closed.
- The deprecated Windhawk rollback source remains untouched.

---

### Task 1: Immediate terminal tap dispatch

**Files:**
- Modify: `tests/test_patch_keymap.py`
- Modify: `scripts/patch_keymap.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `_patch_triple_tap_text_tools(content: str) -> tuple[str, dict[str, int]]`
- Produces: generated C callbacks using `moonlander_<dance>_terminal_fired` state flags

- [x] **Step 1: Write the failing tests**

Add assertions that the patched language `on_dance` callback contains:

```python
self.assertIn("state->count == 2", language_on)
self.assertIn("tap_code16(KC_F22);", language_on)
self.assertIn("moonlander_language_terminal_fired", language_on)
```

Add equivalent count-three assertions for `KC_F19` and `KC_F13`. Assert that finished handlers contain an early fired-flag guard and no marked terminal `case`, and reset handlers clear the corresponding flag. Keep the existing preservation, renumbering, and idempotence assertions.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m unittest tests.test_patch_keymap.TripleTapPatchTests -v
```

Expected: FAIL because the current `on_dance` callbacks are no-ops and `F19`/`F13` remain in delayed finished cases.

- [x] **Step 3: Implement guarded immediate callbacks**

Inject three static flags once:

```c
static bool moonlander_language_terminal_fired;
static bool moonlander_left_space_terminal_fired;
static bool moonlander_right_space_terminal_fired;
```

Generate each terminal callback in this form:

```c
if (state->count == terminal_count && !terminal_fired) {
    tap_code16(terminal_keycode);
    terminal_fired = true;
}
(void)user_data;
```

Insert this guard at the beginning of each matching finished handler:

```c
if (terminal_fired) {
    dance_state[dance_index].step = MORE_TAPS;
    return;
}
```

Insert this guard at the beginning of each matching reset handler:

```c
if (terminal_fired) {
    terminal_fired = false;
    return;
}
```

Remove any previously marked delayed `TRIPLE_TAP` terminal cases so upgrading an already-patched keymap is idempotent.

- [x] **Step 4: Run focused and complete tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_patch_keymap.TripleTapPatchTests -v
python -m unittest discover -s tests -v
```

Expected: all tests pass with no errors or warnings.

- [x] **Step 5: Verify first-pass and second-pass generated output**

Patch a temporary copy of `tests/fixtures/oryx_thumb_dances_unpatched.c`, patch the result again, and assert byte-for-byte equality. Confirm immediate actions occur only in the three intended `on_dance` callbacks and the deprecated Windhawk source is unchanged.

- [x] **Step 6: Update documentation**

Update `README.md` to state that language transplantation fires on the second press, space text tools fire on the third press, and surplus taps are ignored while the internal tap-dance window closes.

- [x] **Step 7: Commit the implementation**

```powershell
git add scripts/patch_keymap.py tests/test_patch_keymap.py README.md docs/superpowers/plans/2026-07-19-immediate-thumb-tap-actions.md
git commit -m "Fire Moonlander text tools at terminal tap"
```
