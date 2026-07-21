# Hebrew Base-Layer Colour

> **Implemented in the repository.** The earlier Layer 5 turquoise design compiled in workflow run [`29808688464`](https://github.com/YiftahCooper/Moonlander-Custom-Config/actions/runs/29808688464). This revision replaces that source with the brown used by Layer 2's black MIDI keys and requires a new workflow run and physical flash acceptance.

## Goal

Use the existing language-sync state to make Hebrew visually obvious across the Moonlander's base layer without overwriting colours deliberately assigned to individual keys in Oryx.

## Approved Behaviour

- English leaves Oryx layer 0 completely unchanged.
- Hebrew replaces only the dominant non-black colour in Oryx Layer 0 with the shared colour of Layer 2's ten black/accidental MIDI melody keys. In the current layout this source colour is `HSV {12, 255, 255}`, the brown selected by the owner.
- Every other Oryx colour remains unchanged, including the language key colour configured manually in Oryx.
- Caps Lock remains able to override its key after the language overlay is applied.
- Layers above layer 0 remain unchanged.
- The overlay follows the existing RAW HID Windows-language state and uses the firmware-local state only when RAW HID is unavailable.
- The former blue/red single-key language indicator is removed.

## Firmware Design

`patch_keymap.py` parses Oryx's generated `ledmap[0]` and `ledmap[2]`. It finds Layer 0's unique most-frequent non-black HSV triplet and injects it as `MOONLANDER_BASE_H/S/V`. It then reads the ten fixed Moonlander LED positions corresponding to the black MIDI melody keys, requires all ten to share one non-black HSV triplet, and injects that value as `MOONLANDER_HEBREW_H/S/V`. This keeps Oryx as the colour source of truth without using a frequency heuristic that could silently choose another MIDI colour.

The generated `rgb_matrix_indicators_user()` calls `custom_language_rgb_overlay()` after Oryx has rendered the layer but before its Caps Lock override. The overlay returns immediately for English or non-base layers. For Hebrew it inspects the original Layer 0 HSV entry for every LED and recolours only exact matches for the detected base triplet. It renders the detected black-MIDI-key HSV through Oryx's existing `hsv_to_rgb_with_value()` function, so hue, saturation, configured value, and global brightness match those keys exactly.

## Failure and Compatibility Behaviour

- Patching fails if Layer 0 has no unique dominant non-black colour, Layer 2 is too short to contain the required semantic LED positions, the ten black MIDI keys disagree, or their shared source colour is black. It must not guess either language colour.
- A manually coloured language key is preserved because its HSV value does not match the dominant base triplet.
- Re-running the patcher produces byte-identical output.
- Existing F18 language switching, CopyQ text tools, MIDI behavior, higher-layer colours, and the deprecated Windhawk rollback source are unchanged.

## Tests

Regression tests cover Layer 0 dominant-colour detection, semantic black-MIDI-key detection, unrelated Layer 2 colours, inconsistent or black source keys, canonical six-macro injection, legacy indicator-hook removal, hook ordering before Caps Lock, second-pass idempotence, and the custom overlay's exact-match use of Oryx's brightness-aware HSV renderer.
