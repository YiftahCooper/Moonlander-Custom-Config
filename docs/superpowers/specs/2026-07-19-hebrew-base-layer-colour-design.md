# Hebrew Base-Layer Colour

## Goal

Use the existing language-sync state to make Hebrew visually obvious across the Moonlander's base layer without overwriting colours deliberately assigned to individual keys in Oryx.

## Approved Behaviour

- English leaves Oryx layer 0 completely unchanged.
- Hebrew replaces only the dominant non-black colour in Oryx layer 0 with the former English-indicator blue, `RGB {40, 140, 255}`.
- Every other Oryx colour remains unchanged, including the language key colour that will be configured manually in Oryx.
- Caps Lock remains able to override its key after the language overlay is applied.
- Layers above layer 0 remain unchanged.
- The overlay follows the existing RAW HID Windows-language state and uses the firmware-local state only when RAW HID is unavailable.
- The former blue/red single-key language indicator is removed.

## Firmware Design

`patch_keymap.py` will parse Oryx's generated `ledmap[0]`, find its unique most-frequent non-black HSV triplet, and inject that triplet as `MOONLANDER_BASE_H`, `MOONLANDER_BASE_S`, and `MOONLANDER_BASE_V`. This treats Oryx as the source of truth for the base colour and avoids identifying keys by physical position.

The generated `rgb_matrix_indicators_user()` will call `custom_language_rgb_overlay()` after Oryx has rendered the layer but before its Caps Lock override. The overlay will return immediately for English or non-base layers. For Hebrew it will inspect the original layer-0 HSV entry for every LED and recolour only exact matches for the detected base triplet. The blue RGB value will be scaled by the keyboard's current global brightness.

## Failure and Compatibility Behaviour

- Patching fails if layer 0 has no unique dominant non-black colour; it must not guess which colour is the base.
- A manually coloured language key is preserved because its HSV value does not match the dominant base triplet.
- Re-running the patcher produces byte-identical output.
- Existing F18 language switching, CopyQ text tools, MIDI behavior, higher-layer colours, and the deprecated Windhawk rollback source are unchanged.

## Tests

Regression tests cover dominant-colour detection, black/off exclusion, ambiguous-colour failure, canonical macro injection, legacy indicator-hook removal, hook ordering before Caps Lock, second-pass idempotence, and the custom overlay's exact-match and brightness-scaled blue behavior.
