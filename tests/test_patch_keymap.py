import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("patch_keymap", ROOT / "scripts" / "patch_keymap.py")
PATCH_KEYMAP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PATCH_KEYMAP)


def load_fixture() -> str:
    return (ROOT / "3aMQz" / "keymap.c").read_text(encoding="utf-8")


def load_unpatched_oryx_fixture() -> str:
    return (ROOT / "tests" / "fixtures" / "oryx_thumb_dances_unpatched.c").read_text(
        encoding="utf-8"
    )


def renumber_dances(content: str, mapping: dict[int, int]) -> str:
    for old in mapping:
        content = content.replace(f"dance_{old}", f"dance_TMP_{old}")
        content = content.replace(f"dance_state[{old}]", f"dance_state[TMP_{old}]")
    for old, new in mapping.items():
        content = content.replace(f"dance_TMP_{old}", f"dance_{new}")
        content = content.replace(f"dance_state[TMP_{old}]", f"dance_state[{new}]")
    return content


class TripleTapPatchTests(unittest.TestCase):
    def test_fresh_oryx_thumb_export_gets_the_complete_required_mapping(self):
        patched, modifier_changes = PATCH_KEYMAP._patch_modifier_only_thumb_keys(
            load_unpatched_oryx_fixture()
        )
        patched, language_changed = PATCH_KEYMAP._patch_f18_language_dance(patched)
        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(patched)

        self.assertEqual(modifier_changes, 2)
        self.assertTrue(language_changed)
        self.assertEqual(targets, {"language": 0, "left_space": 1, "right_space": 2})
        self.assertIn("MT(MOD_RCTL, KC_NO)", patched)
        self.assertIn("MT(MOD_LSFT | MOD_LCTL, KC_NO)", patched)
        self.assertIn("case SINGLE_TAP: register_code16(KC_F18);", patched)
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LEFT_CTRL);", patched)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_F22);", patched)
        language_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_0")
        left_space_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_1")
        right_space_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_2")
        self.assertIn("state->count == 2", language_on)
        self.assertIn("tap_code16(KC_F22);", language_on)
        self.assertIn("state->count == 3", left_space_on)
        self.assertIn("tap_code16(KC_F19);", left_space_on)
        self.assertIn("state->count == 3", right_space_on)
        self.assertIn("tap_code16(KC_F13);", right_space_on)
        language, _ = PATCH_KEYMAP._get_function_body(patched, "dance_0_finished")
        self.assertNotIn("case TRIPLE_TAP", language)

    def test_missing_language_double_case_fails_instead_of_silently_patching(self):
        fixture = load_unpatched_oryx_fixture().replace(
            "        case DOUBLE_TAP: register_code16(KC_F22); break;\n",
            "",
            1,
        )

        with self.assertRaisesRegex(RuntimeError, "(?i)language.*double"):
            PATCH_KEYMAP._patch_f18_language_dance(fixture)

    def test_previous_language_triple_case_is_removed_as_a_complete_line(self):
        body = (
            "\n    switch (dance_state[0].step) {\n"
            "        case SINGLE_TAP: register_code16(KC_F18); break;\n"
            "        case TRIPLE_TAP: tap_code16(KC_F22); break; "
            "/* ORYX_TEXT_TOOLS_TRIPLE_ACTION_PATCH_F22 */\n"
            "    }\n"
        )

        cleaned = PATCH_KEYMAP._remove_marked_triple_case(body, "F22")

        self.assertNotIn("TRIPLE_TAP", cleaned)
        self.assertNotIn("*/", cleaned)
        self.assertIn("case SINGLE_TAP", cleaned)

    def test_first_patch_emits_terminal_actions_from_on_each_tap_callbacks(self):
        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())

        self.assertEqual(targets, {"language": 0, "left_space": 1, "right_space": 2})
        self.assertIn("TRIPLE_TAP", patched)
        language_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_0")
        left_space_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_1")
        right_space_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_2")
        self.assertIn("state->count == 2", language_on)
        self.assertIn("tap_code16(KC_F22);", language_on)
        self.assertIn("moonlander_language_terminal_fired", language_on)
        self.assertIn("state->count == 3", left_space_on)
        self.assertIn("tap_code16(KC_F19);", left_space_on)
        self.assertIn("moonlander_left_space_terminal_fired", left_space_on)
        self.assertIn("state->count == 3", right_space_on)
        self.assertIn("tap_code16(KC_F13);", right_space_on)
        self.assertIn("moonlander_right_space_terminal_fired", right_space_on)
        self.assertNotIn("\n */\n", patched)

    def test_finished_and_reset_handlers_suppress_delayed_duplicates(self):
        patched, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())

        for index, flag, keycode in (
            (0, "moonlander_language_terminal_fired", "KC_F22"),
            (1, "moonlander_left_space_terminal_fired", "KC_F19"),
            (2, "moonlander_right_space_terminal_fired", "KC_F13"),
        ):
            finished, _ = PATCH_KEYMAP._get_function_body(
                patched, f"dance_{index}_finished"
            )
            reset, _ = PATCH_KEYMAP._get_function_body(patched, f"dance_{index}_reset")
            self.assertIn(f"if ({flag})", finished)
            self.assertIn(f"dance_state[{index}].step = MORE_TAPS;", finished)
            self.assertNotIn(f"case TRIPLE_TAP: tap_code16({keycode});", finished)
            self.assertIn(f"if ({flag})", reset)
            self.assertIn(f"{flag} = false;", reset)
            self.assertRegex(
                reset,
                rf"(?s)if \({flag}\).*?{flag} = false;.*?"
                rf"dance_state\[{index}\]\.step = 0;.*?return;",
            )

        self.assertEqual(patched.count("static bool moonlander_language_terminal_fired;"), 1)
        self.assertEqual(patched.count("static bool moonlander_left_space_terminal_fired;"), 1)
        self.assertEqual(patched.count("static bool moonlander_right_space_terminal_fired;"), 1)

    def test_second_pass_is_idempotent(self):
        once, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())
        twice, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(once)
        self.assertEqual(twice, once)

    def test_dance_renumbering_does_not_change_signature_detection(self):
        fixture = renumber_dances(load_fixture(), {0: 7, 1: 4, 2: 9})
        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(fixture)

        self.assertEqual(targets, {"language": 7, "left_space": 4, "right_space": 9})
        language, _ = PATCH_KEYMAP._get_function_body(patched, "dance_7_finished")
        language_on, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_7")
        left_space, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_4")
        right_space, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_9")
        self.assertNotIn("case TRIPLE_TAP", language)
        self.assertIn("KC_F22", language_on)
        self.assertIn("KC_F19", left_space)
        self.assertIn("KC_F13", right_space)

    def test_right_space_without_hold_action_is_identified(self):
        fixture = load_unpatched_oryx_fixture().replace(
            "        case SINGLE_HOLD: register_code16(KC_SPACE); break;\n",
            "",
            1,
        )

        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(fixture)

        self.assertEqual(targets["right_space"], 2)
        right_space, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_2")
        self.assertIn("state->count == 3", right_space)
        self.assertIn("tap_code16(KC_F13);", right_space)

    def test_single_hold_and_double_behaviors_are_preserved(self):
        patched, language_changed = PATCH_KEYMAP._patch_f18_language_dance(load_fixture())
        patched, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(patched)
        self.assertTrue(language_changed)
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LEFT_CTRL);", patched)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_F22);", patched)
        self.assertIn("case DOUBLE_TAP: unregister_code16(KC_F22);", patched)
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LEFT_SHIFT);", patched)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_CAPS);", patched)
        self.assertIn("case DOUBLE_TAP: tap_code16(KC_KP_DOT); tap_code16(KC_SPACE);", patched)

    def test_dedicated_thumb_modifiers_have_no_tap_action(self):
        fixture = load_unpatched_oryx_fixture()
        patched, changed = PATCH_KEYMAP._patch_modifier_only_thumb_keys(fixture)

        self.assertEqual(changed, 2)
        self.assertIn("MT(MOD_RCTL, KC_NO)", patched)
        self.assertIn("MT(MOD_LSFT | MOD_LCTL, KC_NO)", patched)
        self.assertNotIn("MT(MOD_RCTL, KC_F22)", patched)
        self.assertNotIn("MT(MOD_LSFT | MOD_LCTL, KC_F19)", patched)

        twice, second_changes = PATCH_KEYMAP._patch_modifier_only_thumb_keys(patched)
        self.assertEqual(second_changes, 0)
        self.assertEqual(twice, patched)

    def test_current_oryx_direct_modifier_keys_are_already_valid(self):
        fixture = load_unpatched_oryx_fixture()
        fixture = fixture.replace("MT(MOD_RCTL, KC_F22)", "KC_RIGHT_CTRL")
        fixture = fixture.replace(
            "MT(MOD_LSFT | MOD_LCTL, KC_F19)",
            "LSFT(KC_LEFT_CTRL)",
        )

        patched, changed = PATCH_KEYMAP._patch_modifier_only_thumb_keys(fixture)

        self.assertEqual(changed, 0)
        self.assertEqual(patched, fixture)

    def test_generated_triple_repeat_is_removed_only_from_target_dances(self):
        patched, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())
        language, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_0")
        left_space, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_1")
        right_space, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_2")
        self.assertNotIn("tap_code16(KC_F18);\n        tap_code16(KC_F18);", language)
        self.assertNotIn("tap_code16(KC_SPACE);", left_space)
        self.assertNotIn("tap_code16(KC_SPACE);", right_space)

        unrelated_before, _ = PATCH_KEYMAP._get_function_body(load_fixture(), "on_dance_3")
        unrelated_after, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_3")
        self.assertEqual(unrelated_after, unrelated_before)

    def test_missing_required_signature_fails_instead_of_guessing(self):
        fixture = load_fixture().replace("register_code16(KC_CAPS)", "register_code16(KC_NO)")
        with self.assertRaisesRegex(RuntimeError, "left-space"):
            PATCH_KEYMAP._patch_triple_tap_text_tools(fixture)


class LanguageRgbOverlayPatchTests(unittest.TestCase):
    def test_current_oryx_base_colour_is_detected_from_layer_zero(self):
        self.assertEqual(
            PATCH_KEYMAP._detect_dominant_layer_hsv(load_fixture(), 0),
            (83, 233, 240),
        )

    def test_current_oryx_hebrew_colour_is_detected_from_layer_five(self):
        self.assertEqual(
            PATCH_KEYMAP._detect_dominant_layer_hsv(load_fixture(), 5),
            (131, 252, 242),
        )

    def test_black_leds_are_excluded_from_base_colour_detection(self):
        fixture = """
const uint8_t PROGMEM ledmap[][RGB_MATRIX_LED_COUNT][3] = {
    [0] = { {0,0,0}, {0,0,0}, {10,20,30}, {10,20,30}, {40,50,60} },
};
"""
        self.assertEqual(
            PATCH_KEYMAP._detect_dominant_layer_hsv(fixture, 0),
            (10, 20, 30),
        )

    def test_ambiguous_requested_layer_colour_fails_instead_of_guessing(self):
        fixture = """
const uint8_t PROGMEM ledmap[][RGB_MATRIX_LED_COUNT][3] = {
    [0] = { {1,2,3} },
    [5] = { {10,20,30}, {10,20,30}, {40,50,60}, {40,50,60} },
};
"""
        with self.assertRaisesRegex(RuntimeError, "(?i)unique.*layer 5.*colour"):
            PATCH_KEYMAP._detect_dominant_layer_hsv(fixture, 5)

    def test_missing_requested_layer_fails_instead_of_using_another_layer(self):
        fixture = """
const uint8_t PROGMEM ledmap[][RGB_MATRIX_LED_COUNT][3] = {
    [0] = { {10,20,30}, {10,20,30} },
};
"""
        with self.assertRaisesRegex(RuntimeError, "(?i)layer 5"):
            PATCH_KEYMAP._detect_dominant_layer_hsv(fixture, 5)

    def test_language_colour_contract_is_injected_once_and_is_idempotent(self):
        fixture = load_fixture().replace(
            "/* ORYX_LANG_BASE_COLOR_PATCH */\n"
            "#define MOONLANDER_BASE_H 83\n"
            "#define MOONLANDER_BASE_S 233\n"
            "#define MOONLANDER_BASE_V 240\n"
            "#define MOONLANDER_HEBREW_H 131\n"
            "#define MOONLANDER_HEBREW_S 252\n"
            "#define MOONLANDER_HEBREW_V 242\n",
            "",
            1,
        )
        once, changed = PATCH_KEYMAP._inject_language_hsv_contract(
            fixture, (83, 233, 240), (131, 252, 242)
        )
        twice, second_changed = PATCH_KEYMAP._inject_language_hsv_contract(
            once, (83, 233, 240), (131, 252, 242)
        )

        self.assertTrue(changed)
        self.assertFalse(second_changed)
        self.assertEqual(twice, once)
        self.assertEqual(once.count("ORYX_LANG_BASE_COLOR_PATCH"), 1)
        self.assertIn("#define MOONLANDER_BASE_H 83", once)
        self.assertIn("#define MOONLANDER_BASE_S 233", once)
        self.assertIn("#define MOONLANDER_BASE_V 240", once)
        self.assertIn("#define MOONLANDER_HEBREW_H 131", once)
        self.assertIn("#define MOONLANDER_HEBREW_S 252", once)
        self.assertIn("#define MOONLANDER_HEBREW_V 242", once)
        self.assertEqual(once.count("#define MOONLANDER_HEBREW_H"), 1)

    def test_legacy_three_macro_contract_is_migrated_without_duplicates(self):
        current_block = (
            "/* ORYX_LANG_BASE_COLOR_PATCH */\n"
            "#define MOONLANDER_BASE_H 83\n"
            "#define MOONLANDER_BASE_S 233\n"
            "#define MOONLANDER_BASE_V 240\n"
            "#define MOONLANDER_HEBREW_H 131\n"
            "#define MOONLANDER_HEBREW_S 252\n"
            "#define MOONLANDER_HEBREW_V 242\n"
        )
        legacy_block = (
            "/* ORYX_LANG_BASE_COLOR_PATCH */\n"
            "#define MOONLANDER_BASE_H 83\n"
            "#define MOONLANDER_BASE_S 233\n"
            "#define MOONLANDER_BASE_V 240\n"
        )
        fixture = load_fixture().replace(current_block, legacy_block, 1)

        migrated, changed = PATCH_KEYMAP._inject_language_hsv_contract(
            fixture, (83, 233, 240), (131, 252, 242)
        )

        self.assertTrue(changed)
        self.assertEqual(migrated.count("ORYX_LANG_BASE_COLOR_PATCH"), 1)
        self.assertEqual(migrated.count("#define MOONLANDER_HEBREW_H 131"), 1)
        self.assertEqual(migrated.count("#define MOONLANDER_HEBREW_S 252"), 1)
        self.assertEqual(migrated.count("#define MOONLANDER_HEBREW_V 242"), 1)

    def test_rgb_hook_migrates_before_caps_lock_and_removes_legacy_indicator(self):
        patched, _ = PATCH_KEYMAP._inject_custom_language_prototypes(load_fixture())
        patched, changed = PATCH_KEYMAP._patch_rgb_indicator_hook(patched)
        body, found = PATCH_KEYMAP._get_function_body(
            patched, "rgb_matrix_indicators_user"
        )

        self.assertTrue(changed)
        self.assertTrue(found)
        self.assertNotIn("custom_language_rgb_indicator", patched)
        self.assertEqual(body.count("custom_language_rgb_overlay();"), 1)
        self.assertLess(
            body.index("custom_language_rgb_overlay();"),
            body.index("if (capslock_active"),
        )

    def test_language_prototypes_are_canonicalized_to_the_overlay(self):
        patched, changed = PATCH_KEYMAP._inject_custom_language_prototypes(
            load_fixture()
        )

        self.assertTrue(changed)
        self.assertIn("void custom_language_rgb_overlay(void);", patched)
        self.assertNotIn("void custom_language_rgb_indicator(void);", patched)
        twice, _ = PATCH_KEYMAP._inject_custom_language_prototypes(patched)
        self.assertEqual(twice, patched)

    def test_custom_code_recolours_only_exact_base_matches_with_layer_five_hsv(self):
        source = (ROOT / "custom_qmk" / "custom_code.c").read_text(encoding="utf-8")

        self.assertIn("void custom_language_rgb_overlay(void)", source)
        self.assertIn("if (!custom_language_is_hebrew())", source)
        self.assertIn("if (keyboard_config.disable_layer_led)", source)
        self.assertIn("get_highest_layer(layer_state) != 0", source)
        self.assertIn("MOONLANDER_BASE_H", source)
        self.assertIn("MOONLANDER_BASE_S", source)
        self.assertIn("MOONLANDER_BASE_V", source)
        self.assertIn("MOONLANDER_HEBREW_H", source)
        self.assertIn("MOONLANDER_HEBREW_S", source)
        self.assertIn("MOONLANDER_HEBREW_V", source)
        self.assertIn("hsv_to_rgb_with_value", source)
        self.assertNotIn("LANGUAGE_HEBREW_BASE_R", source)
        self.assertNotIn("LANGUAGE_HEBREW_BASE_G", source)
        self.assertNotIn("LANGUAGE_HEBREW_BASE_B", source)
        self.assertIn("pgm_read_byte(&ledmap[0][led][0])", source)
        self.assertNotIn("custom_language_indicator_led", source)
        self.assertNotIn("LANGUAGE_ENGLISH_R", source)


if __name__ == "__main__":
    unittest.main()
