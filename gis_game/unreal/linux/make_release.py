"""Wrap an Unreal Linux staged build in a portable Ubuntu download archive.

The stage is produced by Unreal Automation Tool. This script only adds the
user-facing installer and fixes executable bits lost on Windows file systems.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import struct
import tarfile
from pathlib import Path


ARCHIVE_ROOT = "Goat-Island-Skiff-Linux"
RELEASE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
COMPANIONS = (
    ("install.sh", 0o755),
    ("PLAY_ON_UBUNTU.md", 0o644),
)
REQUIRED_DATA_FILES = (
    "greenwood_usgs.json",
    "greenwood_landmarks.json",
    "greenwood_2017_s16m_manifest.json",
    "greenwood_2017_s16m.r16",
)
PRIVATE_STAGE_DIRECTORIES = frozenset({"saved", "intermediate", "deriveddatacache", "crashes", "logs"})
PRIVATE_STAGE_SUFFIXES = frozenset({".log", ".dmp", ".stackdump", ".crash"})
DEBUG_STAGE_SUFFIXES = frozenset({".debug", ".dsym", ".pdb", ".ilk", ".sym", ".symbols"})


def _add_bytes(bundle: tarfile.TarFile, name: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{name}")
    info.mode = mode
    info.size = len(data)
    info.mtime = 0
    bundle.addfile(info, io.BytesIO(data))


def _validate_staged_game(staged: Path) -> None:
    if not (staged / "GISGame.sh").is_file():
        raise ValueError(f"Missing Unreal Linux launcher: {staged / 'GISGame.sh'}")

    binary = staged / "GISGame" / "Binaries" / "Linux" / "GISGame-Linux-Shipping"
    if not binary.is_file() or binary.stat().st_size < 4096:
        raise ValueError(f"Missing or incomplete x86_64 ELF executable: {binary}")
    with binary.open("rb") as source:
        header = source.read(64)
    if header[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError(f"Expected a Linux x86_64 ELF executable: {binary}")
    elf_type, machine = struct.unpack_from("<HH", header, 16)
    program_offset = struct.unpack_from("<Q", header, 32)[0]
    header_size, program_entry_size, program_count = struct.unpack_from("<HHH", header, 52)
    if (
        elf_type not in (2, 3)
        or machine != 62
        or header_size != 64
        or program_offset < 64
        or program_entry_size < 56
        or program_count == 0
        or program_offset + program_entry_size * program_count > binary.stat().st_size
    ):
        raise ValueError(f"Invalid Linux x86_64 ELF executable header: {binary}")
    with binary.open("rb") as source:
        has_load_segment = False
        for index in range(program_count):
            source.seek(program_offset + index * program_entry_size)
            if struct.unpack("<I", source.read(4))[0] == 1:  # PT_LOAD
                has_load_segment = True
                break
    if not has_load_segment:
        raise ValueError(f"The Linux x86_64 ELF executable has no loadable segment: {binary}")

    paks = staged / "GISGame" / "Content" / "Paks"
    if not paks.is_dir():
        raise ValueError("The staged build is missing cooked content in GISGame/Content/Paks")
    has_pak = any(path.is_file() and path.stat().st_size > 0 for path in paks.rglob("*.pak"))
    utocs = list(paks.rglob("*.utoc"))
    ucases = list(paks.rglob("*.ucas"))
    for path in (*utocs, *ucases):
        companion = path.with_suffix(".ucas" if path.suffix == ".utoc" else ".utoc")
        if (
            not path.is_file()
            or path.stat().st_size == 0
            or not companion.is_file()
            or companion.stat().st_size == 0
        ):
            raise ValueError(f"The staged build has incomplete cooked IoStore content: {path.name}")
    has_iostore = bool(utocs)
    if not (has_pak or has_iostore):
        raise ValueError("The staged build has no nonempty cooked .pak or .utoc/.ucas payload")

    data_dir = staged / "GISGame" / "Content" / "Data"
    for name in REQUIRED_DATA_FILES:
        path = data_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"The staged build is missing required Lake Greenwood data: {name}")

    for path in staged.rglob("*"):
        relative = path.relative_to(staged)
        if any(part.lower() in PRIVATE_STAGE_DIRECTORIES for part in relative.parts) or path.suffix.lower() in PRIVATE_STAGE_SUFFIXES:
            raise ValueError(f"The staged build contains a private build artifact: {relative}")


def build_release(staged: Path, output: Path, release_id: str) -> Path:
    """Create one ready-to-extract .tar.gz from a UAT Linux stage."""
    staged = Path(staged).resolve()
    output = Path(output).resolve()
    if not RELEASE_ID_PATTERN.fullmatch(release_id):
        raise ValueError("Release ID must use only letters, numbers, dots, dashes, or underscores")
    _validate_staged_game(staged)
    if staged in output.parents:
        raise ValueError("Write the release archive outside the staged build")

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise FileExistsError(f"Remove the previous incomplete archive before retrying: {partial}")
    try:
        with tarfile.open(partial, "w:gz", compresslevel=6, format=tarfile.PAX_FORMAT) as bundle:
            root = tarfile.TarInfo(ARCHIVE_ROOT)
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            root.mtime = 0
            bundle.addfile(root)
            for path in sorted(staged.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"Unexpected symlink in Windows stage: {path}")
                relative = path.relative_to(staged).as_posix()
                if (
                    any(part.lower().endswith(".dsym") for part in path.relative_to(staged).parts)
                    or path.suffix.lower() in DEBUG_STAGE_SUFFIXES
                    or (path.parent == staged and path.name.startswith("Manifest_") and path.name.endswith("_Linux.txt"))
                ):
                    continue
                info = bundle.gettarinfo(str(path), arcname=f"{ARCHIVE_ROOT}/{relative}")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if path.is_dir():
                    info.mode = 0o755
                    bundle.addfile(info)
                    continue
                info.mode = 0o644
                if path.suffix == ".sh":
                    # Unreal's generated shell scripts may have Windows line endings.
                    content = path.read_bytes().replace(b"\r\n", b"\n")
                    info.size = len(content)
                    info.mode = 0o755
                    bundle.addfile(info, io.BytesIO(content))
                else:
                    with path.open("rb") as source:
                        if "Binaries/Linux" in relative and source.read(4) == b"\x7fELF":
                            info.mode = 0o755
                        source.seek(0)
                        bundle.addfile(info, source)

            source_dir = Path(__file__).resolve().parent
            for name, mode in COMPANIONS:
                content = (source_dir / name).read_bytes()
                if name.endswith(".sh"):
                    content = content.replace(b"\r\n", b"\n")
                _add_bytes(bundle, name, content, mode)
            _add_bytes(bundle, "release-id.txt", (release_id + "\n").encode("ascii"), 0o644)
        os.replace(partial, output)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True, help="UAT Linux archive directory containing GISGame.sh")
    parser.add_argument("--output", type=Path, required=True, help="Destination .tar.gz path")
    parser.add_argument("--release-id", required=True, help="Short version such as 0.1.0-alpha1")
    args = parser.parse_args()
    print(build_release(args.staged, args.output, args.release_id))


if __name__ == "__main__":
    main()
