import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import firmware_release
from scripts.firmware_release import (
    package_release,
    select_firmware,
    validate_geometry,
    validate_layout_id,
    write_manifest,
)


class OryxRevisionParsingTests(unittest.TestCase):
    @staticmethod
    def payload(qmk_version: object = "25.0", title: object = "Keyboard layout edited.") -> dict[str, object]:
        return {
            "data": {
                "layout": {
                    "revision": {
                        "hashId": "v6Grvl",
                        "qmkVersion": qmk_version,
                        "title": title,
                    }
                }
            }
        }

    def test_accepts_oryx_integer_valued_string_version(self):
        self.assertTrue(
            hasattr(firmware_release, "parse_oryx_revision"),
            "parse_oryx_revision must normalize Oryx's qmkVersion schema",
        )
        self.assertEqual(
            firmware_release.parse_oryx_revision(self.payload()),
            {
                "hash_id": "v6Grvl",
                "firmware_version": 25,
                "change_description": "Keyboard layout edited.",
            },
        )

    def test_accepts_numeric_integer_version_and_sanitizes_title(self):
        parsed = firmware_release.parse_oryx_revision(
            self.payload(25.0, "Keyboard\r\nlayout edited.")
        )

        self.assertEqual(parsed["firmware_version"], 25)
        self.assertEqual(parsed["change_description"], "Keyboard  layout edited.")

    def test_rejects_graphql_errors_and_non_integer_versions(self):
        invalid_payloads = (
            {"errors": [{"message": "layout unavailable"}]},
            self.payload(25.5),
            self.payload("25.5"),
            self.payload(True),
            self.payload("firmware25"),
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                firmware_release.parse_oryx_revision(payload)

    def test_parse_oryx_response_cli_outputs_normalized_json(self):
        with tempfile.TemporaryDirectory() as temp:
            response_path = Path(temp) / "response.json"
            response_path.write_text(json.dumps(self.payload()), encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                result = firmware_release.main(
                    ["parse-oryx-response", "--response", str(response_path)]
                )

        self.assertEqual(result, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "hash_id": "v6Grvl",
                "firmware_version": 25,
                "change_description": "Keyboard layout edited.",
            },
        )


class InputValidationTests(unittest.TestCase):
    def test_accepts_known_layout_and_geometry(self):
        self.assertEqual(validate_layout_id("3aMQz"), "3aMQz")
        self.assertEqual(validate_geometry("moonlander/reva"), "moonlander/reva")

    def test_rejects_unsafe_layout_identifiers(self):
        for value in ("", " 3aMQz", "3aMQz ", "3aMQz;echo bad", "../3aMQz", "3a/MQz"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_layout_id(value)

    def test_rejects_unknown_geometry(self):
        with self.assertRaises(ValueError):
            validate_geometry("moonlander/unknown")


class FirmwareSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def candidate(self, name: str, content: bytes = b"firmware") -> Path:
        path = self.root / name
        path.write_bytes(content)
        return path

    def test_requires_exactly_one_candidate(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            select_firmware([], "moonlander/reva", "3aMQz")
        first = self.candidate("zsa_moonlander_reva_3aMQz.bin")
        second = self.candidate("zsa_moonlander_reva_3aMQz-copy.bin")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            select_firmware([first, second], "moonlander/reva", "3aMQz")

    def test_rejects_empty_wrong_name_and_moonlander_hex(self):
        empty = self.candidate("zsa_moonlander_reva_3aMQz.bin", b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            select_firmware([empty], "moonlander/reva", "3aMQz")
        wrong = self.candidate("zsa_moonlander_reva_other.bin")
        with self.assertRaisesRegex(ValueError, "name"):
            select_firmware([wrong], "moonlander/reva", "3aMQz")
        hex_file = self.candidate("zsa_moonlander_reva_3aMQz.hex")
        with self.assertRaisesRegex(ValueError, r"\.bin"):
            select_firmware([hex_file], "moonlander/reva", "3aMQz")

    def test_accepts_one_matching_moonlander_binary(self):
        candidate = self.candidate("zsa_moonlander_reva_3aMQz.bin")
        self.assertEqual(
            select_firmware([candidate], "moonlander/reva", "3aMQz"),
            candidate,
        )


class FirmwarePackagingTests(unittest.TestCase):
    @staticmethod
    def complete_metadata() -> dict[str, object]:
        return {
            "build": {"compiler": "gcc", "container_base": "digest", "python": "3"},
            "oryx": {"layout_id": "3aMQz", "geometry": "moonlander/reva", "qmk_version": 24, "revision": "rev"},
            "source": {"repository": "owner/repo", "commit": "source"},
            "zsa_qmk": {"branch": "firmware24", "commit": "qmk"},
            "verification": {"level": "ci-verified-candidate", "hardware_flash_witnessed": False},
        }

    def test_manifest_is_canonical_and_release_package_is_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qmk = root / "qmk"
            qmk.mkdir()
            firmware = qmk / "zsa_moonlander_reva_3aMQz.bin"
            firmware.write_bytes(b"known firmware bytes")
            elf = qmk / ".build" / "zsa_moonlander_reva_3aMQz.elf"
            elf.parent.mkdir()
            elf.write_bytes(b"elf")
            dist = root / "dist"
            metadata = {
                "build": {"compiler": "gcc", "container_base": "debian@sha256:abc", "python": "3"},
                "oryx": {
                    "layout_id": "3aMQz",
                    "geometry": "moonlander/reva",
                    "qmk_version": 24,
                    "revision": "oryx-revision",
                },
                "source": {"repository": "owner/repo", "commit": "source-commit"},
                "zsa_qmk": {"branch": "firmware24", "commit": "qmk-commit"},
                "verification": {
                    "level": "ci-verified-candidate",
                    "hardware_flash_witnessed": False,
                },
            }

            receipt = package_release(qmk, dist, metadata)

            expected_sha = hashlib.sha256(firmware.read_bytes()).hexdigest()
            expected_names = {
                firmware.name,
                f"{firmware.name}.sha256",
                f"{firmware.name}.manifest.json",
            }
            self.assertEqual({path.name for path in dist.iterdir()}, expected_names)
            self.assertEqual(receipt["sha256"], expected_sha)
            manifest_path = dist / f"{firmware.name}.manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact"]["size_bytes"], len(firmware.read_bytes()))
            self.assertEqual(manifest["artifact"]["sha256"], expected_sha)
            self.assertTrue(manifest_path.read_bytes().endswith(b"\n"))
            self.assertEqual(
                (dist / f"{firmware.name}.sha256").read_text(encoding="utf-8"),
                f"{expected_sha}  {firmware.name}\n",
            )

    def test_packaging_requires_corresponding_elf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qmk = root / "qmk"
            qmk.mkdir()
            (qmk / "zsa_moonlander_reva_3aMQz.bin").write_bytes(b"firmware")
            with self.assertRaisesRegex(ValueError, "ELF"):
                package_release(
                    qmk,
                    root / "dist",
                    self.complete_metadata(),
                )

    def test_packaging_rejects_unproved_hardware_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qmk = root / "qmk"
            qmk.mkdir()
            firmware = qmk / "zsa_moonlander_reva_3aMQz.bin"
            firmware.write_bytes(b"firmware")
            elf = qmk / ".build" / "zsa_moonlander_reva_3aMQz.elf"
            elf.parent.mkdir()
            elf.write_bytes(b"elf")
            metadata = self.complete_metadata()
            metadata["verification"] = {
                "level": "hardware-accepted",
                "hardware_flash_witnessed": True,
            }
            with self.assertRaisesRegex(ValueError, "CI-verified"):
                package_release(qmk, root / "dist", metadata)

    def test_write_manifest_sorts_keys_and_ends_with_newline(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            write_manifest(path, {"z": 1, "a": 2})
            self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "a": 2,\n  "z": 1\n}\n')


if __name__ == "__main__":
    unittest.main()
