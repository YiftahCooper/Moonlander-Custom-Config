#!/usr/bin/env python3
"""Validation and packaging helpers for Moonlander firmware releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Mapping


SUPPORTED_GEOMETRIES = frozenset(
    {
        "voyager",
        "moonlander/reva",
        "moonlander/revb",
        "ergodox_ez",
        "ergodox_ez/m32u4/glow",
        "ergodox_ez/m32u4/shine",
        "ergodox_ez/stm32",
        "ergodox_ez/stm32/glow",
        "ergodox_ez/stm32/shine",
        "planck_ez",
        "planck_ez/glow",
    }
)


def validate_layout_id(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("layout ID must contain only letters, digits, underscores, or hyphens")
    return value


def validate_geometry(value: str) -> str:
    if value not in SUPPORTED_GEOMETRIES:
        raise ValueError("unsupported keyboard geometry")
    return value


def select_firmware(candidates: list[Path], geometry: str, layout_id: str) -> Path:
    validate_geometry(geometry)
    validate_layout_id(layout_id)
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one firmware candidate, found {len(candidates)}")
    candidate = candidates[0]
    normalized_geometry = geometry.replace("/", "_")
    if normalized_geometry not in candidate.name or layout_id not in candidate.name:
        raise ValueError("firmware candidate name does not match geometry and layout ID")
    if geometry.startswith("moonlander/") and candidate.suffix.lower() != ".bin":
        raise ValueError("Moonlander firmware must be a .bin file")
    if candidate.suffix.lower() not in {".bin", ".hex"}:
        raise ValueError("firmware candidate must use .bin or .hex")
    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise ValueError("firmware candidate is missing or empty")
    return candidate


def write_manifest(path: Path, metadata: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_metadata(metadata: Mapping[str, object]) -> None:
    required_sections = {
        "build": ("compiler", "container_base", "python"),
        "oryx": ("geometry", "layout_id", "qmk_version", "revision"),
        "source": ("repository", "commit"),
        "zsa_qmk": ("branch", "commit"),
        "verification": ("hardware_flash_witnessed", "level"),
    }
    for section, keys in required_sections.items():
        value = metadata.get(section)
        if not isinstance(value, Mapping):
            raise ValueError(f"manifest metadata is missing {section}")
        for key in keys:
            if key not in value or value[key] in (None, ""):
                raise ValueError(f"manifest metadata is missing {section}.{key}")
    verification = metadata["verification"]
    assert isinstance(verification, Mapping)
    if (
        verification["level"] != "ci-verified-candidate"
        or verification["hardware_flash_witnessed"] is not False
    ):
        raise ValueError("release packaging can only claim a CI-verified candidate")


def package_release(qmk_dir: Path, dist_dir: Path, metadata: Mapping[str, object]) -> dict[str, object]:
    _validate_metadata(metadata)
    oryx = metadata["oryx"]
    assert isinstance(oryx, Mapping)
    geometry = str(oryx["geometry"])
    layout_id = str(oryx["layout_id"])
    candidates = sorted((*qmk_dir.glob("*.bin"), *qmk_dir.glob("*.hex")))
    firmware = select_firmware(candidates, geometry, layout_id)
    matching_elfs = sorted((qmk_dir / ".build").rglob(f"{firmware.stem}.elf"))
    if len(matching_elfs) != 1 or not matching_elfs[0].is_file() or matching_elfs[0].stat().st_size == 0:
        raise ValueError("expected exactly one non-empty corresponding ELF file")
    if dist_dir.exists():
        raise ValueError("distribution directory already exists; use a fresh destination")
    dist_dir.mkdir(parents=True)
    destination = dist_dir / firmware.name
    shutil.copy2(firmware, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    size_bytes = destination.stat().st_size
    manifest = dict(metadata)
    manifest["artifact"] = {
        "filename": destination.name,
        "sha256": digest,
        "size_bytes": size_bytes,
    }
    manifest_path = dist_dir / f"{destination.name}.manifest.json"
    checksum_path = dist_dir / f"{destination.name}.sha256"
    write_manifest(manifest_path, manifest)
    checksum_path.write_text(f"{digest}  {destination.name}\n", encoding="utf-8", newline="\n")
    return {
        "firmware": str(destination),
        "manifest": str(manifest_path),
        "checksum": str(checksum_path),
        "elf": str(matching_elfs[0]),
        "sha256": digest,
        "size_bytes": size_bytes,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-inputs")
    validate.add_argument("--layout-id", required=True)
    validate.add_argument("--geometry", required=True)
    package = subparsers.add_parser("package")
    package.add_argument("--qmk-dir", required=True, type=Path)
    package.add_argument("--dist-dir", required=True, type=Path)
    package.add_argument("--metadata", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-inputs":
            validate_layout_id(args.layout_id)
            validate_geometry(args.geometry)
            return 0
        if args.command == "package":
            metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
            receipt = package_release(args.qmk_dir, args.dist_dir, metadata)
            print(json.dumps(receipt, sort_keys=True))
            return 0
    except ValueError as exc:
        print(f"Invalid firmware input: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
