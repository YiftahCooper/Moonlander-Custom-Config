# Immediate Thumb Tap Actions

> **Implemented and compiled successfully.** The terminal actions are present in the firmware built by workflow run [`29808688464`](https://github.com/YiftahCooper/Moonlander-Custom-Config/actions/runs/29808688464).

## Goal

Remove the user-visible QMK tap-dance settlement delay from the three Moonlander text-tool triggers while preserving every established single-tap, hold, and lower-count action.

## Behavior

- Language key: emit `F22` once when the second tap is pressed.
- Left space key: emit `F19` once when the third tap is pressed.
- Right space key: emit `F13` once when the third tap is pressed.
- After a terminal action fires, additional taps in the same tap-dance window are ignored.
- The tap dance is not reset early. Its ordinary timeout closes the gesture silently, preventing a surplus tap from starting a new single-tap action.
- Language single tap remains `F18`; language hold remains Left Ctrl.
- Left-space single, hold, and double remain Space, Left Shift, and Caps Lock.
- Right-space single and double remain Space and period-space.

## Firmware Design

The patcher replaces only the generated `on_dance_<n>()` callbacks for the three signature-detected thumb dances. Each callback checks the terminal count and a per-dance fired flag. At the terminal count it emits the appropriate F-key and sets the flag.

The matching `dance_<n>_finished()` handler detects the fired flag, classifies the dance as `MORE_TAPS`, and returns without emitting the delayed action. The matching reset handler clears the flag and returns without unregistering a key that was already emitted with `tap_code16()`.

The existing `dance_step()` state model remains responsible for all non-terminal single, hold, and double behavior. Dance indices remain discovered by behavior signature rather than hard-coded numbers.

## Safety and Failure Behavior

- A terminal F-key is emitted at most once per tap-dance window.
- Surplus taps cannot produce Space, Caps Lock, period-space, `F18`, or a second text transformation.
- A held terminal press still fires because QMK's `on_each_tap_fn` runs on key press. This is intentional for minimum latency.
- If any required generated callback or behavior signature cannot be identified, patching fails rather than modifying an uncertain dance.
- The deprecated Windhawk rollback implementation remains untouched.

## Tests

Python patcher tests verify:

- `F22` is emitted from the language `on_dance` callback at count two.
- `F19` and `F13` are emitted from their space `on_dance` callbacks at count three.
- Each callback has an at-most-once fired guard.
- Finished handlers suppress delayed duplicate actions after immediate firing.
- Reset handlers clear the fired guard without unregistering terminal F-keys.
- Single, hold, and ordinary double actions remain unchanged.
- Dance renumbering and second-pass idempotence still work.
- Generated Oryx triple-repeat fallbacks remain removed.

The complete Python test suite and a first/second patch pass over the downloaded Oryx snapshot are required before every publication.
