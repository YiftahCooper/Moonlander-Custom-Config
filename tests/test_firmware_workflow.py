import subprocess
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fetch-and-build-layout.yml"
GITIGNORE = ROOT / ".gitignore"
DOCKERFILE = ROOT / "Dockerfile"
README = ROOT / "README.md"
GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("Git is required for firmware workflow contract tests")


class FirmwareWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_qmk_checkout_is_not_a_repository_gitlink(self):
        staged = subprocess.run(
            [GIT, "ls-files", "--stage", "qmk_firmware"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        self.assertNotRegex(staged, r"^160000 ")

    def test_qmk_runtime_clone_is_ignored_and_uses_runner_temp(self):
        self.assertIn("/qmk_firmware/", GITIGNORE.read_text(encoding="utf-8"))
        self.assertIn('echo "QMK_DIR=${RUNNER_TEMP}/qmk_firmware"', self.workflow)
        self.assertNotIn("echo 'QMK_DIR=", self.workflow)

    def test_inputs_are_validated_before_network_access(self):
        validation = "python3 scripts/firmware_release.py validate-inputs"
        self.assertIn(validation, self.workflow)
        self.assertLess(self.workflow.index(validation), self.workflow.index("https://oryx.zsa.io/graphql"))
        self.assertIn("LAYOUT_ID: ${{ github.event.inputs.layout_id }}", self.workflow)
        self.assertIn("LAYOUT_GEOMETRY: ${{ github.event.inputs.layout_geometry }}", self.workflow)

    def test_oryx_download_fails_closed_and_validates_schema(self):
        self.assertGreaterEqual(self.workflow.count("--fail-with-body"), 2)
        self.assertGreaterEqual(self.workflow.count("--retry-all-errors"), 2)
        self.assertIn(
            "python3 scripts/firmware_release.py parse-oryx-response",
            self.workflow,
        )
        self.assertIn("--response response.json", self.workflow)
        self.assertNotIn(".data.layout.revision.qmkVersion | numbers", self.workflow)
        self.assertIn("unzip -t source.zip", self.workflow)
        for required in ("oryx_source/keymap.c", "oryx_source/config.h", "oryx_source/rules.mk"):
            self.assertIn(f'test -f "{required}"', self.workflow)

    def test_repository_tests_precede_qmk_resolution(self):
        tests = "python3 -m unittest discover -s tests -v"
        qmk = "qmk_branch=\"firmware${FIRMWARE_VERSION}\""
        self.assertIn(tests, self.workflow)
        self.assertIn(qmk, self.workflow)
        self.assertLess(self.workflow.index(tests), self.workflow.index(qmk))

    def test_downloaded_source_patch_is_proven_idempotent(self):
        self.assertEqual(self.workflow.count("python3 scripts/patch_keymap.py oryx_source"), 2)
        self.assertIn("first_digest=", self.workflow)
        self.assertIn("second_digest=", self.workflow)
        self.assertIn('test "${first_digest}" = "${second_digest}"', self.workflow)

    def test_qmk_resolution_is_exact_and_never_falls_back_to_master(self):
        self.assertNotIn("defaulting to master", self.workflow)
        self.assertNotIn("git checkout master", self.workflow)
        self.assertIn('refs/heads/${qmk_branch}:refs/remotes/origin/${qmk_branch}', self.workflow)
        self.assertIn('git -C "${QMK_DIR}" checkout --detach "${qmk_commit}"', self.workflow)
        self.assertIn("qmk_commit=${qmk_commit}", self.workflow)

    def test_build_environment_is_dated_and_records_exact_identity(self):
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("FROM debian:bookworm-20260713-slim", dockerfile)
        self.assertRegex(dockerfile, r"qmk==[0-9]")
        self.assertRegex(dockerfile, r"appdirs==[0-9]")
        pull = 'docker pull --quiet "${base_tag}"'
        inspect = 'docker image inspect "${base_tag}"'
        self.assertIn(pull, self.workflow)
        self.assertIn(inspect, self.workflow)
        self.assertLess(self.workflow.index(pull), self.workflow.index(inspect))
        self.assertIn("RepoDigests", self.workflow)
        self.assertIn("arm-none-eabi-gcc --version", self.workflow)
        self.assertIn("python3 --version", self.workflow)

    def test_packaging_requires_manifest_checksum_and_elf_evidence(self):
        self.assertIn("scripts/firmware_release.py package", self.workflow)
        self.assertIn("arm-none-eabi-size", self.workflow)
        self.assertIn(".manifest.json", self.workflow)
        self.assertIn(".sha256", self.workflow)

    def test_actions_are_pinned_and_release_is_non_overwriting(self):
        self.assertIn("actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10", self.workflow)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", self.workflow)
        self.assertIn("softprops/action-gh-release@c12583777ecdfd3be55c69cf75464299dc01057e", self.workflow)
        self.assertIn("if-no-files-found: error", self.workflow)
        self.assertIn("overwrite_files: false", self.workflow)
        self.assertIn("target_commitish: ${{ github.sha }}", self.workflow)

    def test_release_identity_and_published_assets_are_verified(self):
        self.assertIn("source_short=\"${GITHUB_SHA:0:12}\"", self.workflow)
        self.assertIn("qmk_short=\"${QMK_COMMIT:0:12}\"", self.workflow)
        self.assertIn("CI-verified candidate; physical flash not yet witnessed", self.workflow)
        self.assertIn('gh release view "${RELEASE_TAG}"', self.workflow)
        self.assertIn("sha256sum --check", self.workflow)
        self.assertIn("stat -c '%s'", self.workflow)
        self.assertIn("actual_size=", self.workflow)

    def test_readme_distinguishes_ci_candidate_from_hardware_acceptance(self):
        readme = README.read_text(encoding="utf-8")
        self.assertIn("CI-verified candidate", readme)
        self.assertIn("Hardware accepted", readme)
        self.assertIn("manifest", readme)
        self.assertNotIn("qmk_firmware/           ← ZSA QMK fork (submodule", readme)


if __name__ == "__main__":
    unittest.main()
