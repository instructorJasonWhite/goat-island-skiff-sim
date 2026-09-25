"""Checks for the Ubuntu package built from the portable Linux release."""

import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import make_release
from test_make_release import DATA_FILES, make_stage


@unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb is required")
class UbuntuDebTests(unittest.TestCase):
    def build_package(self, archive: Path, package: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("make_deb.py")), "--archive", str(archive), "--output", str(package)],
            capture_output=True,
            text=True,
        )

    def test_deb_installs_game_launcher_and_menu_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = make_release.build_release(make_stage(root), root / "game.tar.gz", "0.1.0-alpha1")
            package = root / "game.deb"

            build = self.build_package(archive, package)
            self.assertEqual(build.returncode, 0, build.stderr)

            self.assertEqual(subprocess.check_output(["dpkg-deb", "-f", str(package), "Package"], text=True).strip(), "goat-island-skiff")
            self.assertEqual(subprocess.check_output(["dpkg-deb", "-f", str(package), "Version"], text=True).strip(), "0.1.0~alpha1")
            self.assertEqual(subprocess.check_output(["dpkg-deb", "-f", str(package), "Architecture"], text=True).strip(), "amd64")
            dependencies = subprocess.check_output(["dpkg-deb", "-f", str(package), "Depends"], text=True)
            self.assertIn("libvulkan1", dependencies)
            self.assertNotIn("nvidia", dependencies.lower())
            self.assertNotIn("mesa", dependencies.lower())
            listing = subprocess.check_output(["dpkg-deb", "-c", str(package)], text=True)
            self.assertTrue(all(" root/root " in line for line in listing.splitlines()), listing[:2000])
            self.assertTrue(listing.splitlines()[0].startswith("drwxr-xr-x "), listing.splitlines()[0])

            extracted = root / "extracted"
            subprocess.run(["dpkg-deb", "-x", str(package), str(extracted)], check=True)
            payload = extracted / "opt/goat-island-skiff"
            self.assertTrue((payload / "GISGame/Binaries/Linux/GISGame-Linux-Shipping").stat().st_mode & 0o111)
            self.assertTrue((extracted / "usr/bin/goat-island-skiff").stat().st_mode & 0o111)
            self.assertTrue((extracted / "usr/share/applications/goat-island-skiff-ubuntu.desktop").is_file())
            for name in DATA_FILES:
                self.assertEqual((payload / "GISGame/Content/Data" / name).read_bytes(), b"map data")
            self.assertFalse((payload / "install.sh").exists())

    def test_rejects_unsafe_archive_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                release = tarfile.TarInfo("Goat-Island-Skiff-Linux/release-id.txt")
                release.size = len(b"0.1.0-alpha1\n")
                bundle.addfile(release, io.BytesIO(b"0.1.0-alpha1\n"))
                member = tarfile.TarInfo("Goat-Island-Skiff-Linux/../../escape")
                member.size = 5
                bundle.addfile(member, io.BytesIO(b"hello"))

            build = self.build_package(archive, root / "game.deb")
            self.assertNotEqual(build.returncode, 0)
            self.assertRegex(build.stderr, "unsafe|Unexpected|escape")
            self.assertFalse((root / "escape").exists())
            self.assertFalse((root / "game.deb").exists())


if __name__ == "__main__":
    unittest.main()
