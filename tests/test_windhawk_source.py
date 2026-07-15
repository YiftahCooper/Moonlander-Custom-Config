from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "host_tools" / "windhawk" / "moonlander_language_sync.wh.cpp"
LEGACY_SOURCE = (
    ROOT
    / "host_tools"
    / "windhawk"
    / "deprecated"
    / "moonlander_language_sync_with_text_tools_v1.2.8.deprecated.wh.cpp"
)


class WindhawkOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_windhawk_retains_f18_language_switching(self):
        self.assertIn("RegisterHotKey(nullptr, kHotkeyIdF18", self.source)
        self.assertIn("trigger_language_shortcut();", self.source)

    def test_windhawk_retains_raw_hid_rgb_synchronization(self):
        self.assertIn("kOryxStatusLedControlCommand", self.source)
        self.assertIn("send_language_state_to_keyboards", self.source)

    def test_windhawk_no_longer_owns_copyq_text_tool_hotkeys(self):
        self.assertNotIn("kHotkeyIdF19", self.source)
        self.assertNotIn("kHotkeyIdF22", self.source)
        self.assertNotIn("VK_F19", self.source)
        self.assertNotIn("VK_F22", self.source)

    def test_windhawk_contains_no_clipboard_or_text_transformation_code(self):
        self.assertNotIn("OpenClipboard", self.source)
        self.assertNotIn("send_ctrl_c", self.source)
        self.assertNotIn("cycle_case", self.source)
        self.assertNotIn("fix_wrong_language", self.source)
        self.assertNotIn("reselect_after_paste", self.source)

    def test_deprecated_legacy_text_tool_source_is_preserved(self):
        self.assertTrue(LEGACY_SOURCE.is_file(), "Legacy Windhawk rollback source must be preserved")
        legacy = LEGACY_SOURCE.read_text(encoding="utf-8")
        self.assertIn("DEPRECATED", legacy)
        self.assertIn("moonlander-language-sync-legacy-deprecated", legacy)
        self.assertIn("OpenClipboard", legacy)
        self.assertIn("VK_F19", legacy)
        self.assertIn("VK_F22", legacy)


if __name__ == "__main__":
    unittest.main()
