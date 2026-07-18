Exit code: 0
Wall time: 0.7 seconds
Total output lines: 1829
Output:
import os
import re
import sys
from typing import Callable

PATCH_MARKER = "ORYX_FN24_NUMDOT_SPACE_PATCH"
MIDI_ENUM_MARKER = "ORYX_MIDI_KEYCODE_ENUM_PATCH"
MIDI_LAYER_MARKER = "ORYX_MIDI_LAYER2_PATCH"
# The MIDI keys live on layer 2 (confirmed against the live Oryx export).
MIDI_LAYER_INDEX = 2
LANGUAGE_TOGGLE_MARKER = "ORYX_LANG_TOGGLE_PATCH"
LANGUAGE_RESYNC_MARKER = "ORYX_LANG_RESYNC_PATCH"
LANGUAGE_RGB_MARKER = "ORYX_LANG_RGB_PATCH"
LANGUAGE_HOLD_PREF_MARKER = "ORYX_LANG_HOLD_PREF_PATCH"
LANGUAGE_ON_DANCE_NOOP_MARKER = "ORYX_LANG_ON_DANCE_NOOP_PATCH"
LANGUAGE_TAP_TERM_MARKER = "ORYX_LANG_TAP_TERM_PATCH"
LANGUAGE_F18_HOLD_MARKER = "ORYX_LANG_F18_HOLD_PREF_PATCH"
LANGUAGE_F22_DOUBLETAP_MARKER = "ORYX_LANG_F22_DOUBLETAP_PATCH"
TAPHOLD_COMPAT_MARKER = "ORYX_TAPHOLD_FALLBACK_PATCH"
DOUBLETAP_COMPAT_MARKER = "ORYX_DOUBLETAP_FALLBACK_PATCH"
SPACESHIFT_HOLD_PREF_MARKER = "ORYX_SPACESHIFT_HOLD_PREF_PATCH"
SPACE_DOT_TERM_MARKER = "ORYX_SPACE_DOT_TERM_PATCH"
TRIPLE_TAP_ENUM_MARKER = "ORYX_TEXT_TOOLS_TRIPLE_ENUM_PATCH"
TRIPLE_TAP_STEP_MARKER = "ORYX_TEXT_TOOLS_TRIPLE_STEP_PATCH"
TRIPLE_TAP_ON_DANCE_MARKER = "ORYX_TEXT_TOOLS_TRIPLE_ON_DANCE_PATCH"
TRIPLE_TAP_ACTION_MARKER = "ORYX_TEXT_TOOLS_TRIPLE_ACTION_PATCH"
LANGUAGE_SWITCH_TAPPING_TERM_MS = 2000
SPACE_DOT_TERM_SCALE_NUM = 6
SPACE_DOT_TERM_SCALE_DEN = 5
# Keep per-key tap windows from collapsing into impractically short ranges.
MAX_TAPPING_TERM_SUBTRACT = 40
RELAX_AGGRESSIVE_TAPPING_TERMS = True


def _find_matching_brace(content: str, open_idx: int) -> int:
    """
    Return index of the matching '}' for the '{' at open_idx.
    Skips braces inside strings and comments to keep block matching stable.
    """
    if open_idx < 0 or open_idx >= len(content) or content[open_idx] != "{":
        return -1

    depth = 0
    i = open_idx
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    while i < len(content):
        ch = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "'":
            in_char = True
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
            if depth < 0:
                return -1
        i += 1

    return -1


def _find_matching_paren(content: str, open_idx: int) -> int:
    """
    Return index of the matching ')' for the '(' at open_idx.
    Skips parens inside strings, char literals, and comments.
    """
    if open_idx < 0 or open_idx >= len(content) or content[open_idx] != "(":
        return -1

    depth = 0
    i = open_idx
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    while i < len(content):
        ch = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "'":
            in_char = True
            i += 1
            continue

        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
            if depth < 0:
                return -1
        i += 1

    return -1


def _replace_function_body(content: str, function_name: str, body: str) -> str:
    function_pat = re.compile(rf"\b{re.escape(function_name)}\s*\([^)]*\)\s*\{{")
    m = function_pat.search(content)
    if not m:
        return content

    open_brace_idx = content.find("{", m.start())
    if open_brace_idx == -1:
        return content

    close_brace_idx = _find_matching_brace(content, open_brace_idx)
    if close_brace_idx == -1:
        return content

    return content[: open_brace_idx + 1] + body + content[close_brace_idx:]


def _get_function_body(content: str, function_name: str) -> tuple[str, bool]:
    function_pat = re.compile(rf"\b{re.escape(function_name)}\s*\([^)]*\)\s*\{{")
    m = function_pat.search(content)
    if not m:
        return "", False

    open_brace_idx = content.find("{", m.start())
    if open_brace_idx == -1:
        return "", False

    close_brace_idx = _find_matching_brace(content, open_brace_idx)
    if close_brace_idx == -1:
        return "", False

    return content[open_brace_idx + 1 : close_brace_idx], True


def _discover_dance_indices(content: str) -> list[int]:
    """
    Discover tap-dance indices present in the generated keymap so downstream
    patch passes do not repeatedly scan a hardcoded numeric range.
    """
    indices = {
        int(m.group(1))
        for m in re.finditer(r"\bdance_(\d+)_(?:finished|reset)\s*\(", content)
    }
    if indices:
        return sorted(indices)
    # Fallback for unexpected source layouts.
    return list(range(0, 24))


def _find_unique_dance_by_signature(
    content: str,
    dance_indices: list[int],
    label: str,
    signature: Callable[[str], bool],
) -> int:
    matches = []
    for dance_idx in dance_indices:
        body, found = _get_function_body(content, f"dance_{dance_idx}_finished")
        if found and signature(body):
            matches.append(dance_idx)

    if len(matches) != 1:
        raise RuntimeError(
            f"Could not uniquely identify {label} tap dance by behavior signature; "
            f"found {matches or 'none'}"
        )
    return matches[0]


def _insert_triple_case(body: str, action: str, marker_suffix: str) -> str:
    marker = f"{TRIPLE_TAP_ACTION_MARKER}_{marker_suffix}"
    if marker in body:
        return body

    switch_close = body.rfind("}")
    if switch_close == -1:
        raise RuntimeError("Tap-dance handler has no switch block for TRIPLE_TAP")

    case_indent_match = re.search(r"^(?P<indent>[ \t]*)case\s+SINGLE_TAP\s*:", body, re.MULTILINE)
    if not case_indent_match:
        raise RuntimeError("Tap-dance handler has no SINGLE_TAP case")
    indent = case_indent_match.group("indent")
    triple_case = f"{indent}case TRIPLE_TAP: {action} break; /* {marker} */\n"
    return body[:switch_close] + triple_case + body[switch_close:]


def _remove_marked_triple_case(body: str, marker_suffix: str) -> str:
    marker = f"{TRIPLE_TAP_ACTION_MARKER}_{marker_suffix}"
    return re.sub(
        rf"^[ \t]*case\s+TRIPLE_TAP\s*:[^\r\n]*{re.escape(marker)}[^\r\n]*(?:\r?\n|$)",
        "",
        body,
        flags=re.MULTILINE,
    )


def _patch_triple_tap_text_tools(content: str) -> tuple[str, dict[str, int]]:
    """
    Add deterministic triple-tap host triggers to the two space dances.

    Targets are discovered from their single/hold/double behavior, never their
    generated DANCE_n indices. Generated count==3 repeat callbacks are disabled
    for the language and space dances. The language key deliberately has no
    triple-tap action; transplantation is its double tap. A held third tap and
    four-or-more taps resolve to MORE_TAPS, for which these handlers have no
    action.
    """
    dance_indices = _discover_dance_indices(content)
    language_idx = _find_unique_dance_by_signature(
        content,
        dance_indices,
        "language/Ctrl",
        lambda body: (
            "case SINGLE_TAP:" in body
            and "KC_F18" in body
            and "case SINGLE_HOLD: register_code16(KC_LEFT_CTRL);" in body
        ),
    )
    left_space_idx = _find_unique_dance_by_signature(
        content,
        dance_indices,
        "left-space/Shift/Caps Lock",
        lambda body: (
            "case SINGLE_TAP: register_code16(KC_SPACE);" in body
            and "case SINGLE_HOLD: register_code16(KC_LEFT_SHIFT);" in body
            and "case DOUBLE_TAP: register_code16(KC_CAPS);" in body
        ),
    )
    right_space_idx = _find_unique_dance_by_signature(
        content,
        dance_indices,
        "right-space/period-space",
        lambda body: (
            "case SINGLE_TAP: register_code16(KC_SPACE);" in body
            and "case DOUBLE_TAP:" in body
            and (
                "tap_code16(KC_KP_DOT); tap_code16(KC_SPACE);" in body
                or "KC_F24" in body
            )
        ),
    )

    targets = {
        "language": language_idx,
        "left_space": left_space_idx,
        "right_space": right_space_idx,
    }
    if len(set(targets.values())) != 3:
        raise RuntimeError(f"Triple-tap behavior signatures overlap: {targets}")

    if TRIPLE_TAP_ENUM_MARKER not in content:
        enum_pattern = re.compile(r"^(?P<indent>[ \t]*)MORE_TAPS(?P<comma>\s*,?)", re.MULTILINE)
        replacement = (
            rf"\g<indent>TRIPLE_TAP, /* {TRIPLE_TAP_ENUM_MARKER} */\n"
            r"\g<indent>MORE_TAPS\g<comma>"
        )
        content, replaced = enum_pattern.subn(replacement, content, count=1)
        if replaced != 1:
            raise RuntimeError("Could not add TRIPLE_TAP to the Oryx dance-state enum")

    dance_step_body = (
        "\n"
        "    if (state->count == 1) {\n"
        "        if (state->interrupted || !state->pressed) return SINGLE_TAP;\n"
        "        return SINGLE_HOLD;\n"
        "    } else if (state->count == 2) {\n"
        "        if (state->interrupted) return DOUBLE_SINGLE_TAP;\n"
        "        if (state->pressed) return DOUBLE_HOLD;\n"
        "        return DOUBLE_TAP;\n"
        "    } else if (state->count == 3) {\n"
        f"        if (state->interrupted || !state->pressed) return TRIPLE_TAP; /* {TRIPLE_TAP_STEP_MARKER} */\n"
        "        return MORE_TAPS;\n"
        "    }\n"
        "    return MORE_TAPS;\n"
    )
    if not _get_function_body(content, "dance_step")[1]:
        raise RuntimeError("Could not find Oryx dance_step function")
    content = _replace_function_body(content, "dance_step", dance_step_body)

    for dance_idx in targets.values():
        on_name = f"on_dance_{dance_idx}"
        on_body, has_on = _get_function_body(content, on_name)
        if not has_on:
            raise RuntimeError(f"Missing generated {on_name} callback")
        if TRIPLE_TAP_ON_DANCE_MARKER not in on_body:
            no_op_body = (
                "\n"
                "    // Multi-tap actions are resolved only by dance_step().\n"
                "    (void)state;\n"
                f"    (void)user_data; /* {TRIPLE_TAP_ON_DANCE_MARKER} */\n"
            )
            content = _replace_function_body(content, on_name, no_op_body)

    # Migrate the previous, incorrect language-triple implementation.
    for function_name in (
        f"dance_{language_idx}_finished",
        f"dance_{language_idx}_reset",
    ):
        body, found = _get_function_body(content, function_name)
        if not found:
            raise RuntimeError(f"Missing generated {function_name} callback")
        content = _replace_function_body(
            content,
            function_name,
            _remove_marked_triple_case(body, "F22"),
        )

    actions = {
        left_space_idx: ("tap_code16(KC_F19);", "F19"),
        right_space_idx: ("tap_code16(KC_F13);", "F13"),
    }
    for dance_idx, (action, suffix) in actions.items():
        finished_name = f"dance_{dance_idx}_finished"
        finished_body, has_finished = _get_function_body(content, finished_name)
        if not has_finished:
            raise RuntimeError(f"Missing generated {finished_name} callback")
        finished_body = _insert_triple_case(finished_body, action, suffix)
        content = _replace_function_body(content, finished_name, finished_body)

        reset_name = f"dance_{dance_idx}_reset"
        reset_body, has_reset = _get_function_body(content, reset_name)
        if not has_reset:
            raise RuntimeError(f"Missing generated {reset_name} callback")
        reset_body = _insert_triple_case(reset_body, "", suffix)
        content = _replace_function_body(content, reset_name, reset_body)

    return content, targets


def _patch_modifier_only_thumb_keys(content: str) -> tuple[str, int]:
    """Keep the two auxiliary left-thumb keys modifier-only."""
    replacements = (
        (
            re.compile(r"MT\(\s*MOD_RCTL\s*,\s*KC_(?:F22|NO)\s*\)"),
            re.compile(r"\bKC_RIGHT_CTRL\b"),
            "MT(MOD_RCTL, KC_NO)",
            "Right Ctrl",
        ),
        (
            re.compile(
                r"MT\(\s*(?:MOD_LSFT\s*\|\s*MOD_LCTL|MOD_LCTL\s*\|\s*MOD_LSFT)\s*,\s*KC_(?:F19|NO)\s*\)"
            ),
            re.compile(r"LSFT\(\s*KC_LEFT_CTRL\s*\)"),
            "MT(MOD_LSFT | MOD_LCTL, KC_NO)",
            "Shift+Ctrl",
        ),
    )
    patched = content
    changed = 0
    for legacy_pattern, direct_pattern, replacement, label in replacements:
        legacy_matches = list(legacy_pattern.finditer(patched))
        direct_matches = list(direct_pattern.finditer(patched))
        if not legacy_matches and len(direct_matches) == 1:
            continue
        if len(legacy_matches) != 1 or direct_matches:
            raise RuntimeError(
                f"Could not uniquely identify the {label} modifier-only thumb key; "
                f"found {len(legacy_matches) + len(direct_matches)} matches"
            )
        match = legacy_matches[0]
        original = match.group(0)
        patched = patched[:match.start()] + replacement + patched[match.end():]
        if original != replacement:
            changed += 1
    return patched, changed


def _replace_case_block(body: str, case_name: str, replacement_builder: Callable[[str], str]) -> tuple[str, bool]:
    """
    Replace one switch-case block while preserving indentation.
    """
    case_pat = re.compile(
        rf"(?P<indent>^[ \t]*)case\s+{re.escape(case_name)}\s*:\s*.*?(?=^[ \t]*case\s+|^[ \t]*default\s*:|}})",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = case_pat.search(body)
    if not match:
        return body, False

    indent = match.group("indent")
    replacement = replacement_builder(indent)
    body_new = case_pat.sub(replacement + "\n", body, count=1)
    return body_new, True


def _replace_fn24_in_space_tap_dance(content: str, dance_indices: list[int]) -> tuple[str, bool]:
    """
    Replace FN24 in the generated right-thumb tap dance with:
      DOUBLE_TAP and DOUBLE_SINGLE_TAP => num-dot then space.
    Target only dance_<n>_finished/reset function bodies.
    """
    for dance_idx in dance_indices:
        finished_name = f"dance_{dance_idx}_finished"
        reset_name = f"dance_{dance_idx}_reset"

        finished_body, has_finished = _get_function_body(content, finished_name)
        if not has_finished:
            continue

        if "KC_F24" not in finished_body and PATCH_MARKER not in finished_body:
            continue

        finished_body_new = finished_body
        finished_body_new, replaced_double_tap = _replace_case_block(
            finished_body_new,
            "DOUBLE_TAP",
            lambda indent: (
                f"{indent}case DOUBLE_TAP: tap_code16(KC_KP_DOT); tap_code16(KC_SPACE); "
                f"break; /* {PATCH_MARKER} */"
            ),
        )
        finished_body_new, replaced_double_single = _replace_case_block(
            finished_body_new,
            "DOUBLE_SINGLE_TAP",
            lambda indent: (
                f"{indent}case DOUBLE_SINGLE_TAP: tap_code16(KC_KP_DOT); tap_code16(KC_SPACE); "
                f"break; /* {PATCH_MARKER} */"
            ),
        )

        if not replaced_double_tap and not replaced_double_single:
            continue

        content = _replace_function_body(content, finished_name, finished_body_new)

        reset_body, has_reset = _get_function_body(content, reset_name)
        if has_reset:
            reset_body_new = reset_body
            reset_body_new, _ = _replace_case_block(
                reset_body_new,
                "DOUBLE_TAP",
                lambda indent: f"{indent}case DOUBLE_TAP: break; /* {PATCH_MARKER} */",
            )
            reset_body_new, _ = _replace_case_block(
                reset_body_new,
                "DOUBLE_SINGLE_TAP",
                lambda indent: f"{indent}case DOUBLE_SINGLE_TAP: break; /* {PATCH_MARKER} */",
            )
            content = _replace_function_body(content, reset_name, reset_body_new)

        return content, True

    return content, False


def _inject_custom_language_prototypes(content: str) -> tuple[str, bool]:
    if "void custom_language_toggle(void);" in content:
        return content, True

    if "void custom_language_toggled(void);" in content:
        content = content.replace(
            "void custom_language_toggled(void);\n",
            "void custom_language_toggled(void);\n"
            "void custom_language_toggle(void);\n",
            1,
        )
        return content, True

    prototype_block = (
        "\n// --- Custom language hooks (injected) ---\n"
        "void custom_language_toggled(void);\n"
        "void custom_language_toggle(void);\n"
        "void custom_language_resync(void);\n"
        "void custom_language_rgb_indicator(void);\n"
        "// ----------------------------------------\n"
    )

    include_matches = list(re.finditer(r"^\s*#include[^\n]*\n", content, flags=re.MULTILINE))
    if include_matches:
        insert_idx = include_matches[-1].end()
    else:
  …7895 tokens truncated… missing or not
    72 entries long we fall back to KC_NO / KC_TRANSPARENT placeholders.
    """
    # Indices (flat 0-based) of positions that MUST be overwritten with MIDI notes.
    MIDI_NOTE_INDICES = set()
    # Row 1 sharps (left-bias: sharp sits directly above its natural)
    for i in [14, 15, 17, 18, 19, 21, 22, 24, 25, 26]:
        MIDI_NOTE_INDICES.add(i)
    # Row 2 naturals (all 14)
    for i in range(28, 42):
        MIDI_NOTE_INDICES.add(i)
    # Row 3 bass left (first 6)
    for i in range(42, 48):
        MIDI_NOTE_INDICES.add(i)
    # Row 4 bass left (first 5)
    for i in range(54, 59):
        MIDI_NOTE_INDICES.add(i)
    # Row 5 shifters + 12th bass key
    MIDI_NOTE_INDICES.add(66)   # k50 = BASS12 (MI_B2, left thumb cluster)
    MIDI_NOTE_INDICES.add(67)   # k51 = MIDI_BASS_SHIFT_UP
    MIDI_NOTE_INDICES.add(68)   # k52 = MIDI_BASS_SHIFT_DOWN

    # Build the default fallback (what we'd inject if no Oryx source available).
    DEFAULTS = ["KC_NO"] * 72
    # Row 1 sharps (left-bias: each sharp sits directly above the natural it sharpens)
    sharp_map = {14:"MI_Cs3",15:"MI_Ds3",17:"MI_Fs3",18:"MI_Gs3",19:"MI_As3",
                 21:"MI_Db4",22:"MI_Eb4",24:"MI_Gb4",25:"MI_Ab4",26:"MI_Bb4"}
    for idx, kc in sharp_map.items():
        DEFAULTS[idx] = kc
    # Row 2 naturals
    naturals_left  = ["MI_C3","MI_D3","MI_E3","MI_F3","MI_G3","MI_A3","MI_B3"]
    naturals_right = ["MI_C4","MI_D4","MI_E4","MI_F4","MI_G4","MI_A4","MI_B4"]
    for i, kc in enumerate(naturals_left):
        DEFAULTS[28 + i] = kc
    for i, kc in enumerate(naturals_right):
        DEFAULTS[35 + i] = kc
    # Row 3 bass
    bass_row3 = ["MI_C2","MI_Cs2","MI_D2","MI_Ds2","MI_E2","MI_F2"]
    for i, kc in enumerate(bass_row3):
        DEFAULTS[42 + i] = kc
    # Row 4 bass (shifted: F#2..A#2 so B2 fits as the 12th thumb key)
    bass_row4 = ["MI_Fs2","MI_G2","MI_Gs2","MI_A2","MI_As2"]
    for i, kc in enumerate(bass_row4):
        DEFAULTS[54 + i] = kc
    # Row 5 shifters + 12th bass key (BASS12 on left thumb cluster)
    DEFAULTS[66] = "MI_B2"
    DEFAULTS[67] = "MIDI_BASS_SHIFT_UP"
    DEFAULTS[68] = "MIDI_BASS_SHIFT_DOWN"

    # Start from defaults, then overlay preserved Oryx keys for non-MIDI positions.
    result = list(DEFAULTS)
    if original_args is not None and len(original_args) == 72:
        for i in range(72):
            if i not in MIDI_NOTE_INDICES:
                val = original_args[i].strip()
                if val:
                    result[i] = val

    # Format into rows matching LAYOUT_moonlander arg order.
    row_sizes = [14, 14, 14, 12, 12, 6]
    lines = []
    offset = 0
    for size in row_sizes:
        chunk = result[offset : offset + size]
        lines.append("    " + ", ".join(chunk) + ",")
        offset += size

    body = "\n".join(lines)
    body = body.rstrip()
    if body.endswith(","):
        body = body[:-1]
    return "\n" + body + "\n  "


def _inject_midi_layer(content: str) -> tuple[str, bool]:
    """
    Overwrite the layer-2 keymap body in place with real MIDI keycodes.

    The Oryx export leaves layer 2 as KC_TRANSPARENT / KC_NO placeholders; this
    rewrites the argument list of `[2] = LAYOUT_moonlander( ... )`. The ledmap
    for layer 2 is already correct from Oryx and is intentionally left untouched.
    """
    if MIDI_LAYER_MARKER in content:
        return content, True

    layer_pat = re.compile(
        rf"\[\s*{MIDI_LAYER_INDEX}\s*\]\s*=\s*LAYOUT(?:_moonlander)?\s*\("
    )
    m = layer_pat.search(content)
    if not m:
        return content, False

    open_paren_idx = content.find("(", m.start())
    if open_paren_idx == -1:
        return content, False

    close_paren_idx = _find_matching_paren(content, open_paren_idx)
    if close_paren_idx == -1:
        return content, False

    # Parse the original (Oryx) layer-2 argument list so we can preserve specific
    # user-configured keys (e.g. the big red thumb "back to layer 0" key at k45).
    inner = content[open_paren_idx + 1 : close_paren_idx]
    original_args = _split_top_level_args(inner)

    new_body = _build_midi_layer_body(original_args if len(original_args) == 72 else None)
    marker = f"  /* {MIDI_LAYER_MARKER} */"
    replacement = (
        content[: open_paren_idx + 1]
        + marker
        + new_body
        + content[close_paren_idx:]
    )
    return replacement, True


def patch_config_h_midi(layout_dir: str) -> None:
    """
    Enable ADVANCED MIDI in config.h (paired with MIDI_ENABLE=yes in rules.mk).

    We use MIDI_ADVANCED (not MIDI_BASIC) because:
      - Only MIDI_ADVANCED routes note keycodes through process_midi(), which
        decodes the note BY KEYCODE VALUE (midi_compute_note) and tracks
        note-on/off. This is what lets the per-key bass shifter forward a
        transposed note keycode and have it sound correctly.
      - MIDI_BASIC instead routes notes through process_music(), which requires
        MIDI mode to be toggled on (MI_ON) and computes notes from MATRIX
        POSITION, ignoring the note keycode entirely.
      - MIDI_ADVANCED is a strict superset of MIDI_BASIC (all note keycodes plus
        octave/transpose/velocity/channel), so it is the future-proof choice.
    """
    config_path = os.path.join(layout_dir, "config.h")
    if not os.path.exists(config_path):
        print(f"Warning: {config_path} not found; cannot inject MIDI_ADVANCED.")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Migrate any previously-injected MIDI_BASIC define to MIDI_ADVANCED.
    basic_pat = re.compile(r"^[ \t]*#define[ \t]+MIDI_BASIC\b.*$", flags=re.MULTILINE)
    if basic_pat.search(content):
        content = basic_pat.sub("#define MIDI_ADVANCED", content)
        # Also fix the stale "Basic MIDI support" comment if present.
        content = content.replace(
            "// Basic MIDI support (paired with MIDI_ENABLE=yes in rules.mk).",
            "// Advanced MIDI support (paired with MIDI_ENABLE=yes in rules.mk).",
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Migrated config.h MIDI_BASIC -> MIDI_ADVANCED")
        return

    if re.search(r"^\s*#define\s+MIDI_ADVANCED\b", content, flags=re.MULTILINE):
        print("config.h already defines MIDI_ADVANCED; skipping.")
        return

    addition = "\n// Advanced MIDI support (paired with MIDI_ENABLE=yes in rules.mk).\n#define MIDI_ADVANCED\n"
    if not content.endswith("\n"):
        content += "\n"
    content += addition

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Injected #define MIDI_ADVANCED into config.h")


def patch_rules_mk_midi(layout_dir: str) -> None:
    """
    Ensure MIDI_ENABLE = yes in rules.mk. Replace any existing MIDI_ENABLE line
    (regardless of its value) or append one if missing.
    """
    rules_path = os.path.join(layout_dir, "rules.mk")
    if not os.path.exists(rules_path):
        print(f"Warning: {rules_path} not found; cannot enable MIDI.")
        return

    with open(rules_path, "r", encoding="utf-8") as f:
        content = f.read()

    midi_line_pat = re.compile(r"^\s*MIDI_ENABLE\s*=.*$", flags=re.MULTILINE)
    if midi_line_pat.search(content):
        new_content = midi_line_pat.sub("MIDI_ENABLE = yes", content, count=1)
        if new_content != content:
            with open(rules_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("Set existing MIDI_ENABLE line to yes in rules.mk")
        else:
            print("MIDI_ENABLE already set to yes in rules.mk")
        return

    if not content.endswith("\n"):
        content += "\n"
    content += "MIDI_ENABLE = yes\n"
    with open(rules_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Appended MIDI_ENABLE = yes to rules.mk")


def patch_config_h_low_latency(layout_dir: str) -> None:
    """
    Inject global low-latency settings into config.h for snappier MIDI (and
    typing) response. These are keyboard-wide and do NOT change any keycode
    behavior on any layer, so they are safe for the whole layout:

      - DEBOUNCE 1: QMK default is 5 ms; the debounce delay is added to every
        key event before it is reported. 1 ms is safe for modern switches and
        removes ~4 ms of latency per note-on/note-off.
      - USB_POLLING_INTERVAL_MS 1: forces 1000 Hz USB reporting (1 ms) so note
        events are delivered to the host as fast as USB Full Speed allows.

    Idempotent: existing definitions are replaced (or added if missing).
    """
    config_path = os.path.join(layout_dir, "config.h")
    if not os.path.exists(config_path):
        print(f"Warning: {config_path} not found; cannot inject low-latency settings.")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    settings = [
        ("DEBOUNCE", "1"),
        ("USB_POLLING_INTERVAL_MS", "1"),
    ]

    additions = []
    for name, value in settings:
        define_pat = re.compile(rf"^[ \t]*#define[ \t]+{name}\b.*$", flags=re.MULTILINE)
        new_line = f"#define {name} {value}"
        if define_pat.search(content):
            new_content = define_pat.sub(new_line, content, count=1)
            if new_content != content:
                content = new_content
                print(f"Updated existing #define {name} -> {value} in config.h")
            else:
                print(f"config.h already defines {name} {value}; skipping.")
        else:
            additions.append(new_line)

    if additions:
        block = (
            "\n// Low-latency settings (global). Faster MIDI/typing response; "
            "safe for all layers.\n" + "\n".join(additions) + "\n"
        )
        if not content.endswith("\n"):
            content += "\n"
        content += block
        print(f"Injected low-latency settings into config.h: {', '.join(a.split()[1] for a in additions)}")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)


def patch_keymap(layout_dir: str) -> None:
    keymap_path = os.path.join(layout_dir, "keymap.c")
    if not os.path.exists(keymap_path):
        print(f"Error: {keymap_path} not found")
        print(f"Contents of {layout_dir}:")
        for f in os.listdir(layout_dir):
            print(f)
        sys.exit(1)

    with open(keymap_path, "r", encoding="utf-8") as f:
        content = f.read()

    print("Found keymap.c, length:", len(content))
    dance_indices = _discover_dance_indices(content)
    print(f"Discovered tap-dance indices: {dance_indices}")

    content, modifier_only_changes = _patch_modifier_only_thumb_keys(content)
    print(
        "Enforced modifier-only left-thumb keys "
        f"({modifier_only_changes} tap bindings removed)"
    )

    # 1) Keep key semantics Oryx-managed, but allow RGB hook injection so
    # custom language indicator state can be driven from host RAW HID updates.
    enable_language_injection = False
    enable_language_rgb_hook_injection = True
    if enable_language_injection or enable_language_rgb_hook_injection:
        # Add forward declarations for custom language hooks.
        content, _ = _inject_custom_language_prototypes(content)
    else:
        print("Skipping language prototype injection (Oryx-managed language behavior).")

    # 2) Replace FN24 behavior only in the corresponding tap-dance function.
    content, replaced = _replace_fn24_in_space_tap_dance(content, dance_indices)
    if replaced:
        print("Replaced KC_F24 tap-dance behavior with KP_DOT+SPACE on double tap")
    elif "KC_F24" in content:
        print("Warning: KC_F24 found, but no matching dance_<n>_finished/reset patch target was found.")
    else:
        print("KC_F24 not present in keymap.c; no FN24 tap-dance replacement needed.")

    # 3) Optional language switch/resync injection.
    if enable_language_injection:
        content, lang_toggle_patched, lang_resync_patched = _patch_language_switch_tap_dance(content, dance_indices)
        if lang_toggle_patched:
            print("Patched language key single-tap toggle behavior")
        else:
            print("Warning: Did not patch language key single-tap toggle behavior.")

        if lang_resync_patched:
            print("Patched language key double-tap resync behavior")
        else:
            print("Warning: Did not patch language key resync behavior.")

    else:
        print("Skipping language tap-dance patching (Oryx-managed language behavior).")

    # 4) Optional RGB indicator hook injection.
    if enable_language_rgb_hook_injection:
        content, rgb_patched = _patch_rgb_indicator_hook(content)
        if rgb_patched:
            print("Patched rgb_matrix_indicators_user with custom language indicator hook")
        else:
            print("Warning: rgb_matrix_indicators_user not found; language RGB indicator hook not applied.")
    else:
        print("Skipping language RGB indicator hook patching (Oryx-managed language behavior).")

    # 4b) Enforce language tap/hold/double semantics.
    content, f18_lang_patched = _patch_f18_language_dance(content)
    if f18_lang_patched:
        print("Patched language dance: tap F18, hold Ctrl, double-tap F22")
    else:
        print("No F18 language dance found to patch (skipping).")

    # 4c) Add deterministic host text-tool triggers to the two space dances.
    # This is intentionally strict: an Oryx export whose behavior signatures no
    # longer match must fail rather than risk patching the wrong physical key.
    content, triple_tap_targets = _patch_triple_tap_text_tools(content)
    print(
        "Patched triple-tap text tools: "
        f"language DANCE_{triple_tap_targets['language']} -> no triple action, "
        f"left-space DANCE_{triple_tap_targets['left_space']} -> F19, "
        f"right-space DANCE_{triple_tap_targets['right_space']} -> F13"
    )

    # 5) For the SPACE/SHIFT dance, prefer hold when interrupted by another key.
    content, spaceshift_hold_pref_patched = _prefer_hold_for_space_shift_dance(content, dance_indices)
    if spaceshift_hold_pref_patched:
        print("Patched SPACE/SHIFT dance to prefer hold on interrupt")
    else:
        print("Warning: Could not patch SPACE/SHIFT hold-preference behavior.")

    # 6) For dances without explicit hold behavior, treat SINGLE_HOLD as SINGLE_TAP.
    content, hold_fallback_count = _normalize_tap_dance_hold_resolution(content, dance_indices)
    if hold_fallback_count > 0:
        print(f"Added SINGLE_HOLD->SINGLE_TAP fallback to {hold_fallback_count} tap-dance handlers")
    else:
        print("No tap-dance SINGLE_HOLD fallback patching required.")

    # 7) For dances without explicit double-hold behavior, treat DOUBLE_SINGLE_TAP
    # as DOUBLE_TAP so interrupted doubles still trigger the double function.
    content, doubletap_fallback_count = _normalize_tap_dance_double_tap_resolution(content, dance_indices)
    if doubletap_fallback_count > 0:
        print(f"Added DOUBLE_SINGLE_TAP->DOUBLE_TAP fallback to {doubletap_fallback_count} tap-dance handlers")
    else:
        print("No tap-dance DOUBLE_SINGLE_TAP fallback patching required.")

    # 8) Keep tapping terms entirely Oryx-managed for now.
    print("Skipping script-level tapping-term overrides (using Oryx tap terms).")
    # Tap-term overrides are intentionally disabled for now.
    # To re-enable, uncomment the block below:
    # content, space_dot_term_patched = _increase_space_dot_tapping_term(content, dance_indices)
    # if space_dot_term_patched:
    #     print("Raised dot+space dance tapping term by ~20%")
    # else:
    #     print("Warning: Could not raise dot+space dance tapping term.")
    #
    # content, language_term_patched = _set_language_switch_tapping_term(content, dance_indices)
    # if language_term_patched:
    #     print(f"Set language switch tapping term to {LANGUAGE_SWITCH_TAPPING_TERM_MS}ms")
    # else:
    #     print("Warning: Could not set language switch tapping term.")
    #
    # if RELAX_AGGRESSIVE_TAPPING_TERMS:
    #     content, tapping_term_changes = _relax_aggressive_tapping_terms(content)
    #     if tapping_term_changes > 0:
    #         print(
    #             f"Relaxed {tapping_term_changes} aggressive per-key tapping-term reductions "
    #             f"(max subtract: {MAX_TAPPING_TERM_SUBTRACT})"
    #         )
    #     else:
    #         print("No aggressive per-key tapping-term reductions required patching.")
    # else:
    #     print("Keeping Oryx per-key tapping terms unchanged.")

    # 8.5) MIDI injection: declare custom bass-shift keycodes (top of file) and
    # overwrite the layer-2 placeholders with real MIDI keycodes.
    content, midi_enum_injected = _inject_midi_keycode_enum(content)
    if midi_enum_injected:
        print("Injected MIDI custom-keycode enum near top of keymap.c")
    else:
        print("Warning: Could not inject MIDI custom-keycode enum.")

    content, midi_layer_injected = _inject_midi_layer(content)
    if midi_layer_injected:
        print(f"Overwrote layer {MIDI_LAYER_INDEX} with MIDI keycodes")
    else:
        print(f"Warning: Could not find layer {MIDI_LAYER_INDEX} to inject MIDI keycodes.")

    # 8.6) Patch keyboard_post_init_user to set MIDI octave=1
    content, midi_octave_patched = _patch_keyboard_post_init_midi_octave(content)
    if midi_octave_patched:
        print("Patched keyboard_post_init_user to set MIDI octave=1")
    else:
        print("Warning: Could not patch keyboard_post_init_user for MIDI octave.")

    # 9) Hook process_record_user
    wrapper_marker = "INJECTED BY ORYX-CUSTOM-MOONLANDER WORKFLOW"
    if wrapper_marker in content and '#include "custom_code.c"' in content:
        print("process_record_user wrapper already injected; skipping reinjection.")
    else:
        pattern = r"bool\s+process_record_user\s*\("
        if not re.search(pattern, content):
            print("Error: Could not find process_record_user in keymap.c")
            print("File start:", content[:500])
            sys.exit(1)

        content = re.sub(pattern, "bool process_record_user_oryx(", content, count=1)

        wrapper_code = (
            "\n\n// ============================================================\n"
            "// INJECTED BY ORYX-CUSTOM-MOONLANDER WORKFLOW\n"
            "// ============================================================\n"
            "bool process_record_user_oryx(uint16_t keycode, keyrecord_t *record);\n"
            '#include "custom_code.c"\n'
            + "\n"
            "bool process_record_user(uint16_t keycode, keyrecord_t *record) {\n"
            "    if (!process_record_user_custom(keycode, record)) {\n"
            "        return false;\n"
            "    }\n"
            "    return process_record_user_oryx(keycode, record);\n"
            "}\n"
        )

        content += wrapper_code

    with open(keymap_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Successfully patched keymap.c")

    # 10) Enable MIDI in the build (config.h + rules.mk).
    patch_config_h_midi(layout_dir)
    patch_rules_mk_midi(layout_dir)

    # 11) Global low-latency tuning (DEBOUNCE, USB polling) for MIDI responsiveness.
    patch_config_h_low_latency(layout_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: patch_keymap.py <layout_dir>")
        sys.exit(1)
    patch_keymap(sys.argv[1])

