# Hebrew Base-Layer Colour

## Goal

Use the existing language-sync state to make Hebrew visually obvious across the Moonlander's base layer without overwriting colours deliberately assigned to individual keys in Oryx.

## Approved Behaviour

- English leaves Oryx layer 0 completely unchanged.
- Hebrew replaces only the dominant non-black colour in Oryx layer 0 with the dominant non-black colour from Oryx layer 5. In the accepted layout this source colour is `HSV {131, 252, 242}`, the more turquoise blue selected by the owner.
- Every other Oryx colour remains unchanged, including the language key colour that will be configured manually in Oryx.
- Caps Lock remains able to override its key after the language overlay is applied.
- Layers above layer 0 remain unchanged.
- The overlay follows the existing RAW HID Windows-language state and uses the firmware-local state only when RAW HID is unavailable.
- The former blue/red single-key language indicator is removed.

## Firmware Design

`patch_keymap.py` will parse Oryx's generated `ledmap[0]` and `ledmap[5]`. It finds the unique most-frequent non-black HSV triplet in each layer, injects the layer-0 value as `MOONLANDER_BASE_H/S/V`, and injects the layer-5 value as `MOONLANDER_HEBREW_H/S/V`. This treats Oryx as the source of truth for both the LEDs to replace and the replacement colour, without identifying keys by physical position or approximating the colour in RGB.

The generated `rgb_matrix_indicators_user()` will call `custom_language_rgb_overlay()` after Oryx has rendered the layer but before its Caps Lock override. The overlay will return immediately for English or non-base layers. For Hebrew it will inspect the original layer-0 HSV entry for every LED and recolour only exact matches for the detected base triplet. It renders the detected layer-5 HSV through Oryx's existing `hsv_to_rgb_with_value()` function, so hue, saturation, configured value, and global brightness match Layer 5 exactly.

## Failure and Compatibility Behaviour

- Patching fails if either layer 0 or layer 5 has no unique dominant non-black colour; it must not guess the base or Hebrew colour.
- A manually coloured language key is preserved because its HSV value does not match the dominant base triplet.
- Re-running the patcher produces byte-identical output.
- Existing F18 language switching, CopyQ text tools, MIDI behavior, higher-layer colours, and the deprecated Windhawk rollback source are unchanged.

## Tests

Regression tests cover dominant-colour detection for layers 0 and 5, black/off exclusion, missing and ambiguous layer failure, canonical six-macro injection, legacy indicator-hook removal, hook ordering before Caps Lock, second-pass idempotence, and the custom overlay's exact-match use of Oryx's brightness-aware HSV renderer.
