"""Release checks catch incomplete or unlaunchable Linux game downloads."""

import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import make_release


DATA_FILES = (
    "greenwood_usgs.json",
    "greenwood_landmarks.json",
    "greenwood_2017_s16m_manifest.json",
    "greenwood_2017_s16m.r16",
)


def make_stage(root: Path) -> Path:
    staged = root / "staged"
    binary = staged / "GISGame" / "Binaries" / "Linux" / "GISGame-Linux-Shipping"
    binary.parent.mkdir(parents=True)
    elf = bytearray(4097)
    elf[:7] = b"\x7fELF\x02\x01\x01"  # ELF64, little endian, current version
    elf[16:18] = (3).to_bytes(2, "little")  # position-independent executable
    elf[18:20] = (62).to_bytes(2, "little")  # x86_64
    elf[32:40] = (64).to_bytes(8, "little")  # program header table offset
    elf[52:54] = (64).to_bytes(2, "little")  # ELF header size
    elf[54:56] = (56).to_bytes(2, "little")  # program header entry size
    elf[56:58] = (1).to_bytes(2, "little")  # one program header
    elf[64:68] = (1).to_bytes(4, "little")  # loadable segment
    binary.write_bytes(elf)
    (staged / "GISGame.sh").write_bytes(b"#!/bin/sh\r\necho game\r\n")
    paks = staged / "GISGame" / "Content" / "Paks"
    paks.mkdir(parents=True)
    (paks / "GISGame-Linux.pak").write_bytes(b"cooked map data")
    data = staged / "GISGame" / "Content" / "Data"
    data.mkdir(parents=True)
    for name in DATA_FILES:
        (data / name).write_bytes(b"map data")
    return staged


class LinuxReleaseTests(unittest.TestCase):
    def test_archive_contains_complete_game_and_executable_launchers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            archive = root / "release.tar.gz"

            make_release.build_release(staged, archive, "0.1.0-test")

            with tarfile.open(archive, "r:gz") as bundle:
                prefix = "Goat-Island-Skiff-Linux/"
                names = set(bundle.getnames())
                for name in DATA_FILES:
                    self.assertIn(prefix + "GISGame/Content/Data/" + name, names)
                self.assertIn(prefix + "install.sh", names)
                self.assertIn(prefix + "PLAY_ON_UBUNTU.md", names)
                self.assertIn(prefix + "release-id.txt", names)
                self.assertIn(prefix + "GISGame/Content/Paks/GISGame-Linux.pak", names)
                self.assertEqual(bundle.extractfile(prefix + "release-id.txt").read(), b"0.1.0-test\n")
                self.assertTrue(bundle.extractfile(prefix + "install.sh").read().startswith(b"#!/usr/bin/env bash\n"))
                self.assertEqual(bundle.extractfile(prefix + "GISGame.sh").read(), b"#!/bin/sh\necho game\n")
                self.assertTrue(bundle.getmember(prefix + "GISGame.sh").mode & 0o111)
                self.assertTrue(bundle.getmember(prefix + "GISGame/Binaries/Linux/GISGame-Linux-Shipping").mode & 0o111)

    def test_missing_game_launcher_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = root / "staged"
            staged.mkdir()
            with self.assertRaisesRegex(ValueError, "GISGame.sh"):
                make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_placeholder_or_wrong_architecture_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            binary = staged / "GISGame/Binaries/Linux/GISGame-Linux-Shipping"
            no_load_segment = bytearray(binary.read_bytes())
            no_load_segment[64:68] = b"\0" * 4
            for invalid in (b"\x7fELFfake game", b"MZWindows binary", b"\x7fELF\x02\x01\x01" + b"\0" * 4090, bytes(no_load_segment)):
                with self.subTest(invalid=invalid[:12]):
                    binary.write_bytes(invalid)
                    with self.assertRaisesRegex(ValueError, "ELF"):
                        make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_missing_or_empty_map_data_is_rejected(self):
        for name in DATA_FILES:
            for missing in (False, True):
                with self.subTest(name=name, missing=missing), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    staged = make_stage(root)
                    data_file = staged / "GISGame/Content/Data" / name
                    if missing:
                        data_file.unlink()
                    else:
                        data_file.write_bytes(b"")
                    with self.assertRaisesRegex(ValueError, name):
                        make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_empty_cooked_payload_or_orphan_iostore_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            pak = staged / "GISGame/Content/Paks/GISGame-Linux.pak"
            pak.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "cooked"):
                make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")
            pak.unlink()
            (pak.parent / "GISGame-Linux.utoc").write_bytes(b"table only")
            with self.assertRaisesRegex(ValueError, "cooked"):
                make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_pak_does_not_hide_an_incomplete_iostore_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            paks = staged / "GISGame/Content/Paks"
            (paks / "GISGame-Linux.utoc").write_bytes(b"table only")
            with self.assertRaisesRegex(ValueError, "cooked"):
                make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_valid_iostore_pair_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            pak = staged / "GISGame/Content/Paks/GISGame-Linux.pak"
            pak.unlink()
            (pak.parent / "GISGame-Linux.utoc").write_bytes(b"table")
            (pak.parent / "GISGame-Linux.ucas").write_bytes(b"cooked content")
            make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

    def test_private_build_artifacts_are_rejected_before_archiving(self):
        for relative in (
            "GISGame/Saved/Logs/GISGame.log",
            "GISGame/Saved/Crashes/diagnostic.dmp",
            "Engine/Intermediate/build.txt",
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                staged = make_stage(root)
                incidental = staged / relative
                incidental.parent.mkdir(parents=True, exist_ok=True)
                incidental.write_text("C:/Users/example/private build path", encoding="utf-8")
                archive = root / "release.tar.gz"

                with self.assertRaisesRegex(ValueError, "private build artifact"):
                    make_release.build_release(staged, archive, "0.1.0-test")
                self.assertFalse(archive.exists())

    def test_unreal_debug_symbols_and_staging_manifests_are_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            binaries = staged / "GISGame/Binaries/Linux"
            (binaries / "GISGame-Linux-Shipping.debug").write_bytes(b"private build paths")
            (binaries / "GISGame-Linux-Shipping.sym").write_bytes(b"private symbols")
            (staged / "Manifest_DebugFiles_Linux.txt").write_text("debug list")
            (staged / "Manifest_UFSFiles_Linux.txt").write_text("staging list")

            archive = make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")

            with tarfile.open(archive, "r:gz") as bundle:
                names = set(bundle.getnames())
                self.assertIn("Goat-Island-Skiff-Linux/GISGame/Binaries/Linux/GISGame-Linux-Shipping", names)
                self.assertFalse(any(name.endswith((".debug", ".sym")) for name in names))
                self.assertFalse(any("Manifest_" in name for name in names))

    def test_installer_is_lf_even_when_source_checkout_is_crlf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            companions = root / "companions"
            companions.mkdir()
            (companions / "install.sh").write_bytes(b"#!/usr/bin/env bash\r\necho install\r\n")
            (companions / "PLAY_ON_UBUNTU.md").write_text("Play", encoding="utf-8")
            with patch.object(make_release, "__file__", str(companions / "make_release.py")):
                archive = make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")
            with tarfile.open(archive, "r:gz") as bundle:
                script = bundle.extractfile("Goat-Island-Skiff-Linux/install.sh").read()
                self.assertEqual(script, b"#!/usr/bin/env bash\necho install\n")

    @unittest.skipUnless(platform.system() == "Linux" and platform.machine() == "x86_64", "Linux install check")
    def test_same_release_id_with_changed_payload_is_rejected_without_replacing_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = make_stage(root)
            archive = make_release.build_release(staged, root / "release.tar.gz", "0.1.0-test")
            with tarfile.open(archive, "r:gz") as bundle:
                options = {"filter": "data"} if sys.version_info >= (3, 12) else {}
                bundle.extractall(root / "extracted", **options)
            package = root / "extracted" / "Goat-Island-Skiff-Linux"
            home = root / "home"
            home.mkdir()
            env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / ".local/share"))

            first = subprocess.run(["bash", str(package / "install.sh")], env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            installed_pak = home / ".local/share/goat-island-skiff/builds/0.1.0-test/GISGame/Content/Paks/GISGame-Linux.pak"
            self.assertEqual(installed_pak.read_bytes(), b"cooked map data")
            (package / "GISGame/Content/Paks/GISGame-Linux.pak").write_bytes(b"changed bytes")

            second = subprocess.run(["bash", str(package / "install.sh")], env=env, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("different", second.stderr.lower())
            self.assertEqual(installed_pak.read_bytes(), b"cooked map data")


if __name__ == "__main__":
    unittest.main()
