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


def renumber_dances(content: str, mapping: dict[int, int]) -> str:
    for old in mapping:
        content = content.replace(f"dance_{old}", f"dance_TMP_{old}")
        content = content.replace(f"dance_state[{old}]", f"dance_state[TMP_{old}]")
    for old, new in mapping.items():
        content = content.replace(f"dance_TMP_{old}", f"dance_{new}")
        content = content.replace(f"dance_state[TMP_{old}]", f"dance_state[{new}]")
    return content


class TripleTapPatchTests(unittest.TestCase):
    def test_first_patch_adds_explicit_triple_state_and_expected_actions(self):
        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())

        self.assertEqual(targets, {"language": 0, "left_space": 1, "right_space": 2})
        self.assertIn("TRIPLE_TAP", patched)
        self.assertIn("case TRIPLE_TAP: tap_code16(KC_F22);", patched)
        self.assertIn("case TRIPLE_TAP: tap_code16(KC_F19);", patched)
        self.assertIn("case TRIPLE_TAP: tap_code16(KC_F13);", patched)

    def test_second_pass_is_idempotent(self):
        once, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())
        twice, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(once)
        self.assertEqual(twice, once)

    def test_dance_renumbering_does_not_change_signature_detection(self):
        fixture = renumber_dances(load_fixture(), {0: 7, 1: 4, 2: 9})
        patched, targets = PATCH_KEYMAP._patch_triple_tap_text_tools(fixture)

        self.assertEqual(targets, {"language": 7, "left_space": 4, "right_space": 9})
        language, _ = PATCH_KEYMAP._get_function_body(patched, "dance_7_finished")
        left_space, _ = PATCH_KEYMAP._get_function_body(patched, "dance_4_finished")
        right_space, _ = PATCH_KEYMAP._get_function_body(patched, "dance_9_finished")
        self.assertIn("KC_F22", language)
        self.assertIn("KC_F19", left_space)
        self.assertIn("KC_F13", right_space)

    def test_single_hold_and_double_behaviors_are_preserved(self):
        patched, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LEFT_CTRL);", patched)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_F18);", patched)
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LEFT_SHIFT);", patched)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_CAPS);", patched)
        self.assertIn("case DOUBLE_TAP: tap_code16(KC_KP_DOT); tap_code16(KC_SPACE);", patched)

    def test_generated_triple_repeat_is_removed_only_from_target_dances(self):
        patched, _ = PATCH_KEYMAP._patch_triple_tap_text_tools(load_fixture())
        for index in (0, 1, 2):
            body, found = PATCH_KEYMAP._get_function_body(patched, f"on_dance_{index}")
            self.assertTrue(found)
            self.assertNotIn("state->count == 3", body)

        unrelated_before, _ = PATCH_KEYMAP._get_function_body(load_fixture(), "on_dance_3")
        unrelated_after, _ = PATCH_KEYMAP._get_function_body(patched, "on_dance_3")
        self.assertEqual(unrelated_after, unrelated_before)

    def test_missing_required_signature_fails_instead_of_guessing(self):
        fixture = load_fixture().replace("register_code16(KC_CAPS)", "register_code16(KC_NO)")
        with self.assertRaisesRegex(RuntimeError, "left-space"):
            PATCH_KEYMAP._patch_triple_tap_text_tools(fixture)


if __name__ == "__main__":
    unittest.main()
