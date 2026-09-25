"""Build an Ubuntu amd64 installer from the existing portable Linux archive.

The package installs the self-contained Unreal game under /opt and adds an
application-menu shortcut. Graphics drivers remain the operating system's job.
Requires dpkg-deb on the build machine.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from make_release import ARCHIVE_ROOT, _validate_staged_game


GAME_DIRECTORY = Path("opt/goat-island-skiff")
RELEASE_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?\Z")
LAUNCH_SCRIPT = b"#!/bin/sh\ncd /opt/goat-island-skiff\nexec ./GISGame/Binaries/Linux/GISGame-Linux-Shipping GISGame \"$@\"\n"
DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Goat Island Skiff
Comment=Sail Lake Greenwood in a Goat Island Skiff
Exec=/usr/bin/goat-island-skiff
Terminal=false
Icon=applications-games
Categories=Game;Simulation;
"""


def _release_version(bundle: tarfile.TarFile) -> str:
    try:
        member = bundle.getmember(f"{ARCHIVE_ROOT}/release-id.txt")
    except KeyError as exc:
        raise ValueError("The Linux archive has no release ID") from exc
    if not member.isfile() or member.size > 128:
        raise ValueError("The Linux archive has an invalid release ID")
    source = bundle.extractfile(member)
    if source is None:
        raise ValueError("The Linux archive has an unreadable release ID")
    try:
        release_id = source.read().decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("The Linux archive has a non-ASCII release ID") from exc
    if not RELEASE_PATTERN.fullmatch(release_id):
        raise ValueError(f"Unsupported Linux release ID: {release_id!r}")
    return release_id.replace("-", "~", 1)


def _extract_game(bundle: tarfile.TarFile, destination: Path) -> None:
    """Copy only safe regular game files from the portable archive."""
    seen: set[str] = set()
    for member in bundle:
        path = PurePosixPath(member.name)
        parts = path.parts
        if (
            not parts
            or parts[0] != ARCHIVE_ROOT
            or path.is_absolute()
            or any(part in (".", "..") for part in parts)
            or member.name in seen
        ):
            raise ValueError(f"Unsafe or unexpected archive member: {member.name}")
        seen.add(member.name)
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Unsafe archive member type: {member.name}")
        if len(parts) == 1:
            if not member.isdir():
                raise ValueError("The Linux archive root is not a directory")
            continue
        if parts[1] in {"install.sh", "PLAY_ON_UBUNTU.md"}:
            continue
        target = destination.joinpath(*parts[1:])
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(0o755)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = bundle.extractfile(member)
        if source is None:
            raise ValueError(f"Unreadable archive file: {member.name}")
        with target.open("xb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o755 if member.mode & 0o111 else 0o644)


def build_deb(archive: Path, output: Path) -> Path:
    """Create one .deb that Ubuntu can install through App Center."""
    archive = Path(archive).resolve()
    output = Path(output).resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Linux release archive not found: {archive}")
    if output.suffix != ".deb":
        raise ValueError("Output filename must end in .deb")
    if archive == output:
        raise ValueError("The package cannot overwrite its source archive")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")
    if partial.exists():
        raise FileExistsError(f"Remove the previous incomplete package before retrying: {partial}")

    try:
        with tempfile.TemporaryDirectory(prefix="goat-island-skiff-deb-") as temp:
            package_root = Path(temp) / "package"
            game = package_root / GAME_DIRECTORY
            game.mkdir(parents=True)
            with tarfile.open(archive, "r:gz") as bundle:
                version = _release_version(bundle)
                _extract_game(bundle, game)
            _validate_staged_game(game)

            # Unreal's generated launcher runs chmod at every start. Package
            # files are root-owned, so both entry points use this safe variant.
            (game / "GISGame.sh").write_bytes(LAUNCH_SCRIPT)
            (game / "GISGame.sh").chmod(0o755)
            bin_dir = package_root / "usr/bin"
            bin_dir.mkdir(parents=True)
            launcher = bin_dir / "goat-island-skiff"
            launcher.write_bytes(b"#!/bin/sh\nexec /opt/goat-island-skiff/GISGame.sh \"$@\"\n")
            launcher.chmod(0o755)
            applications = package_root / "usr/share/applications"
            applications.mkdir(parents=True)
            (applications / "goat-island-skiff-ubuntu.desktop").write_text(DESKTOP_ENTRY, encoding="utf-8")

            installed_size = (sum(path.stat().st_size for path in package_root.rglob("*") if path.is_file()) + 1023) // 1024
            control_dir = package_root / "DEBIAN"
            control_dir.mkdir()
            (control_dir / "control").write_text(
                "Package: goat-island-skiff\n"
                f"Version: {version}\n"
                "Section: games\n"
                "Priority: optional\n"
                "Architecture: amd64\n"
                "Maintainer: Goat Island Skiff Project\n"
                "Depends: libc6 (>= 2.28), libvulkan1\n"
                f"Installed-Size: {installed_size}\n"
                "Homepage: https://mechatronicsaint.com/lab\n"
                "Description: Goat Island Skiff sailing simulator\n"
                " Sail Lake Greenwood in the Goat Island Skiff Unreal game.\n",
                encoding="utf-8",
            )
            for directory in package_root.rglob("*"):
                if directory.is_dir():
                    directory.chmod(0o755)
            package_root.chmod(0o755)
            (control_dir / "control").chmod(0o644)
            (applications / "goat-island-skiff-ubuntu.desktop").chmod(0o644)
            subprocess.run(
                ["dpkg-deb", "--root-owner-group", "-Zxz", "-z6", "--build", str(package_root), str(partial)],
                check=True,
            )
        os.replace(partial, output)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Existing Goat-Island-Skiff-Linux.tar.gz")
    parser.add_argument("--output", type=Path, required=True, help="Destination Ubuntu .deb path")
    arguments = parser.parse_args()
    print(build_deb(arguments.archive, arguments.output))


if __name__ == "__main__":
    main()
