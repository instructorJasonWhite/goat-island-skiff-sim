"""Checks for a complete, clean Windows player download."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import make_release


DATA_FILES = (
    "greenwood_usgs.json",
    "greenwood_landmarks.json",
    "greenwood_2017_s16m_manifest.json",
    "greenwood_2017_s16m.r16",
)


def pe64() -> bytes:
    data = bytearray(4097)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    data[0x80:0x84] = b"PE\0\0"
    data[0x84:0x86] = (0x8664).to_bytes(2, "little")
    return bytes(data)


def stage(root: Path) -> Path:
    staged = root / "stage" / "Windows"
    game = staged / "GISGame"
    binary = game / "Binaries" / "Win64" / "GISGame.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(pe64())
    (staged / "GISGame.exe").write_bytes(pe64())
    paks = game / "Content" / "Paks"
    paks.mkdir(parents=True)
    (paks / "GISGame-Windows.pak").write_bytes(b"cooked game")
    (paks / "GISGame-Windows.utoc").write_bytes(b"table")
    (paks / "GISGame-Windows.ucas").write_bytes(b"cooked bulk data")
    data = game / "Content" / "Data"
    data.mkdir(parents=True)
    for name in DATA_FILES:
        (data / name).write_bytes(b"lake data")
    (staged / "Engine" / "Binaries").mkdir(parents=True)
    (staged / "Engine" / "Binaries" / "runtime.dll").write_bytes(b"runtime")
    (staged / "NOTICES.txt").write_text("license notice", encoding="utf-8")
    return staged


class WindowsReleaseTests(unittest.TestCase):
    def test_archive_contains_launchers_runtime_cooked_content_and_lake(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = stage(root)
            output = root / "Goat-Island-Skiff-Windows.zip"

            make_release.build_release(staged, output, "0.1.0-test")

            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
                prefix = "Goat-Island-Skiff-Windows/"
                for name in (
                    "GISGame.exe",
                    "GISGame/Binaries/Win64/GISGame.exe",
                    "GISGame/Content/Paks/GISGame-Windows.pak",
                    "GISGame/Content/Paks/GISGame-Windows.utoc",
                    "GISGame/Content/Paks/GISGame-Windows.ucas",
                    "Engine/Binaries/runtime.dll",
                    "NOTICES.txt",
                    "PLAY_ON_WINDOWS.md",
                    "release-id.txt",
                ):
                    self.assertIn(prefix + name, names)
                for name in DATA_FILES:
                    self.assertIn(prefix + "GISGame/Content/Data/" + name, names)
                self.assertEqual(archive.read(prefix + "release-id.txt"), b"0.1.0-test\n")
                self.assertEqual(archive.read(prefix + "GISGame.exe"), pe64())

    def test_debug_symbols_saved_logs_manifests_and_secrets_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = stage(root)
            for relative in (
                "GISGame/Binaries/Win64/GISGame.pdb",
                "GISGame/Saved/Logs/GISGame.log",
                "Engine/Intermediate/build.txt",
                "GISGame/Content/Crashes/error.dmp",
                "GISGame/Content/temporary.key",
                ".env",
                "Manifest_DebugFiles_Win64.txt",
                "Manifest_UFSFiles_Win64.txt",
            ):
                path = staged / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private", encoding="utf-8")

            output = make_release.build_release(staged, root / "release.zip", "0.1.0-test")

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertFalse(any("private" in archive.read(name).decode("utf-8", "ignore") for name in names))
                self.assertFalse(any("Manifest_" in name for name in names))
                self.assertIn("Goat-Island-Skiff-Windows/NOTICES.txt", names)

    def test_missing_or_invalid_windows_launchers_are_rejected(self):
        for relative in ("GISGame.exe", "GISGame/Binaries/Win64/GISGame.exe"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                staged = stage(root)
                path = staged / relative
                path.unlink()
                with self.assertRaisesRegex(ValueError, "executable"):
                    make_release.build_release(staged, root / "release.zip", "0.1.0-test")
                path.write_bytes(b"not a Windows program" * 500)
                with self.assertRaisesRegex(ValueError, "PE"):
                    make_release.build_release(staged, root / "release.zip", "0.1.0-test")

    def test_missing_lake_data_or_incomplete_cooked_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = stage(root)
            data = staged / "GISGame/Content/Data/greenwood_usgs.json"
            data.unlink()
            with self.assertRaisesRegex(ValueError, "greenwood_usgs.json"):
                make_release.build_release(staged, root / "release.zip", "0.1.0-test")
            data.write_bytes(b"lake data")
            (staged / "GISGame/Content/Paks/GISGame-Windows.ucas").unlink()
            with self.assertRaisesRegex(ValueError, "IoStore"):
                make_release.build_release(staged, root / "release.zip", "0.1.0-test")

    def test_unsafe_release_id_and_output_inside_stage_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged = stage(root)
            with self.assertRaisesRegex(ValueError, "Release ID"):
                make_release.build_release(staged, root / "release.zip", "../unsafe")
            with self.assertRaisesRegex(ValueError, "outside"):
                make_release.build_release(staged, staged / "release.zip", "0.1.0-test")


if __name__ == "__main__":
    unittest.main()
