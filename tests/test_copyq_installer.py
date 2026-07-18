from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "host_tools" / "copyq" / "Install-MoonlanderTextTools.ps1"


class CopyQInstallerPowerShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INSTALLER.read_text(encoding="utf-8")

    def test_copyq_cli_is_always_waited_for_and_captured_in_powershell(self):
        invocations = re.findall(r"^.*& \$CopyQPath eval --.*$", self.source, re.MULTILINE)
        self.assertEqual(1, len(invocations), "CopyQ CLI calls must use one guarded helper")
        self.assertIn("| Write-Output", invocations[0])

    def test_installer_probes_copyq_before_writing_a_backup(self):
        probe = self.source.index("MOONLANDER_COPYQ_READY")
        backup_write = self.source.index("[IO.File]::WriteAllText(")
        self.assertLess(probe, backup_write)

    def test_installer_verifies_all_three_commands_before_reporting_success(self):
        for name in (
            "Moonlander: Smart Title Case",
            "Moonlander: Cycle Case",
            "Moonlander: Transplant Hebrew-English",
        ):
            self.assertIn(name, self.source)
        self.assertIn("CopyQ command verification failed", self.source)

    def test_installer_reads_back_copyq_14_global_shortcut_lists(self):
        self.assertIn("command.globalShortcuts", self.source)
        self.assertNotRegex(self.source, r"command\.globalShortcut(?!s)")
        for shortcut in ("F13", "F19", "F22"):
            self.assertIn(shortcut, self.source)
        self.assertIn("CopyQ shortcut verification failed", self.source)

    def test_installer_calls_direct_command_definition_api(self):
        self.assertIn(
            "MoonlanderCommandInstaller.install('$installPathForJavaScript', '$helperPathForJavaScript', $activate)",
            self.source,
        )
        self.assertNotIn("importCommands", self.source)
        self.assertNotIn("fromBase64", self.source)


if __name__ == "__main__":
    unittest.main()
