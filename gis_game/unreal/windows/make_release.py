"""Build a portable Windows player ZIP from Unreal's staged Windows game."""

from __future__ import annotations

import argparse
import os
import re
import struct
import zipfile
from pathlib import Path


ARCHIVE_ROOT = "Goat-Island-Skiff-Windows"
RELEASE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
REQUIRED_DATA_FILES = (
    "greenwood_usgs.json",
    "greenwood_landmarks.json",
    "greenwood_2017_s16m_manifest.json",
    "greenwood_2017_s16m.r16",
)
PRIVATE_DIRECTORIES = frozenset(
    {"saved", "intermediate", "deriveddatacache", "crashes", "logs", "__pycache__", ".git"}
)
EXCLUDED_SUFFIXES = frozenset(
    {".pdb", ".ilk", ".sym", ".debug", ".dmp", ".log", ".stackdump", ".crash", ".key", ".pem", ".pfx", ".p12"}
)


def _included(relative: Path) -> bool:
    parts = relative.parts
    if any(part.lower() in PRIVATE_DIRECTORIES for part in parts[:-1]):
        return False
    name = parts[-1].lower()
    if name.startswith("manifest_") or name == ".env" or name.startswith(".env."):
        return False
    return relative.suffix.lower() not in EXCLUDED_SUFFIXES


def _validate_pe64(path: Path) -> None:
    if not path.is_file() or path.stat().st_size < 4096:
        raise ValueError(f"Missing or incomplete Windows executable: {path}")
    with path.open("rb") as source:
        header = source.read(64)
        if header[:2] != b"MZ":
            raise ValueError(f"Expected a Windows x64 PE executable: {path}")
        pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
        if pe_offset < 64 or pe_offset + 6 > path.stat().st_size:
            raise ValueError(f"Invalid Windows x64 PE executable header: {path}")
        source.seek(pe_offset)
        signature_and_machine = source.read(6)
    if signature_and_machine != b"PE\0\0\x64\x86":
        raise ValueError(f"Expected a Windows x64 PE executable: {path}")


def _validate_stage(staged: Path) -> None:
    _validate_pe64(staged / "GISGame.exe")
    _validate_pe64(staged / "GISGame" / "Binaries" / "Win64" / "GISGame.exe")

    paks = staged / "GISGame" / "Content" / "Paks"
    if not paks.is_dir():
        raise ValueError("The staged game is missing cooked content in GISGame/Content/Paks")
    has_pak = any(path.is_file() and path.stat().st_size > 0 for path in paks.rglob("*.pak"))
    utocs = list(paks.rglob("*.utoc"))
    ucases = list(paks.rglob("*.ucas"))
    for path in (*utocs, *ucases):
        companion = path.with_suffix(".ucas" if path.suffix == ".utoc" else ".utoc")
        if path.stat().st_size == 0 or not companion.is_file() or companion.stat().st_size == 0:
            raise ValueError(f"The staged game has incomplete cooked IoStore content: {path.name}")
    if not (has_pak or utocs):
        raise ValueError("The staged game has no nonempty cooked .pak or .utoc/.ucas payload")

    data_dir = staged / "GISGame" / "Content" / "Data"
    for name in REQUIRED_DATA_FILES:
        path = data_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"The staged game is missing required Lake Greenwood data: {name}")


def build_release(staged: Path, output: Path, release_id: str) -> Path:
    """Package a UAT Windows stage without local settings, logs, or symbols."""
    staged = Path(staged).resolve()
    output = Path(output).resolve()
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError("Release ID must use only letters, numbers, dots, dashes, or underscores")
    if output.suffix.lower() != ".zip":
        raise ValueError("Output path must end in .zip")
    if staged == output or staged in output.parents:
        raise ValueError("Write the release archive outside the staged build")
    _validate_stage(staged)

    selected = []
    for path in staged.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink in Windows stage: {path}")
        if path.is_file():
            relative = path.relative_to(staged)
            if _included(relative):
                selected.append((path, relative))

    instructions = (Path(__file__).resolve().parent / "PLAY_ON_WINDOWS.md").read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise FileExistsError(f"Remove the previous incomplete archive before retrying: {partial}")
    expected = {f"{ARCHIVE_ROOT}/{relative.as_posix()}" for _, relative in selected}
    expected.update({f"{ARCHIVE_ROOT}/PLAY_ON_WINDOWS.md", f"{ARCHIVE_ROOT}/release-id.txt"})
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for path, relative in sorted(selected, key=lambda item: item[1].as_posix()):
                archive.write(path, arcname=f"{ARCHIVE_ROOT}/{relative.as_posix()}")
            archive.writestr(f"{ARCHIVE_ROOT}/PLAY_ON_WINDOWS.md", instructions)
            archive.writestr(f"{ARCHIVE_ROOT}/release-id.txt", (release_id + "\n").encode("ascii"))
        with zipfile.ZipFile(partial, "r") as archive:
            damaged = archive.testzip()
            if damaged is not None:
                raise ValueError(f"Release ZIP failed CRC verification: {damaged}")
            if set(archive.namelist()) != expected:
                raise ValueError("Release ZIP contents differ from selected runtime files")
        os.replace(partial, output)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True, help="UAT Windows package folder containing GISGame.exe")
    parser.add_argument("--output", type=Path, required=True, help="Destination .zip path")
    parser.add_argument("--release-id", required=True, help="Short version such as 0.1.0-alpha1")
    args = parser.parse_args()
    print(build_release(args.staged, args.output, args.release_id))


if __name__ == "__main__":
    main()
