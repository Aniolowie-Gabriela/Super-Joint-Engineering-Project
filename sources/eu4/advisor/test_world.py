import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from world import WorldSources


class WorldFilesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write("launcher-settings.json", b'{"gameId":"eu4","rawVersion":"v1.37.5.0"}')

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_polish_text_and_search_continuation(self):
        path = "localisation/test_l_polish.yml"
        self.write(path, 'l_polish:\r\n a:0 "Łódź"\r\n b:0 "Łódź"\r\n'.encode("cp1250"))
        self.write("localisation/utf8_l_polish.yml", 'l_polish:\n c:0 "Łódź"\n'.encode("utf-8-sig"))
        world = WorldSources(self.root)

        page = world.read_file(path, start_line=2, line_count=1)
        self.assertEqual(page["encoding"], "cp1250")
        self.assertEqual(page["lines"][0]["text"], ' a:0 "Łódź"')
        self.assertEqual(page["next_line"], 3)

        first = world.search_files("łódź", "localisation", limit=1)
        second = world.search_files("łódź", "localisation", limit=3, **first["next"])
        self.assertEqual([(r["path"], r["line"]) for r in second["matches"]], [
            (path, 3), ("localisation/utf8_l_polish.yml", 2),
        ])
        self.assertIsNone(second["next"])

    def test_private_paths_and_archive_traversal_are_inaccessible(self):
        self.write("common/legitimate.txt", b"value = 3\n")
        self.write("common/credentials.txt", b"hidden\n")
        self.write("anvil/private.txt", b"hidden\n")
        self.write("map/terrain.bmp", b"hidden\n")
        path = self.root / "dlc/dlc123_name/dlc123.zip"
        path.parent.mkdir(parents=True)
        with ZipFile(path, "w") as archive:
            archive.writestr("events/dlc.txt", "event = { id = example.1 }")
            archive.writestr("../common/legitimate.txt", "hidden\n")
            archive.writestr("common/private/tokens.txt", "hidden\n")
        world = WorldSources(self.root)
        virtual = "dlc/dlc123_name/dlc123.zip!/events/dlc.txt"

        listed = world.list_files(limit=1)
        self.assertEqual(listed["total"], 2)
        self.assertEqual(world.list_files(offset=listed["next_offset"])["files"][0]["path"], virtual)
        self.assertIn("example.1", world.read_file(virtual)["lines"][0]["text"])
        self.assertEqual(world.search_files("example.1", "dlc")["matches"][0]["path"], virtual)
        self.assertEqual(world.search_files("hidden")["matches"], [])
        for denied in (
            "../unrelated.txt", "common/../launcher-settings.json", "common/legitimate.txt:stream",
            "//device/common/legitimate.txt", "anvil/private.txt", "common/credentials.txt", "map/terrain.bmp",
            "dlc/dlc123_name/dlc123.zip!/../common/legitimate.txt",
        ):
            with self.subTest(path=denied), self.assertRaises(ValueError):
                world.read_file(denied)

    def test_hardlink_is_skipped_even_after_file_was_listed(self):
        allowed = self.write("common/rule.txt", b"value = 3\n")
        outside = self.write("unrelated.txt", b"hidden\n")
        world = WorldSources(self.root)
        self.assertEqual(world.list_files()["total"], 1)
        allowed.unlink()
        try:
            allowed.hardlink_to(outside)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaises(ValueError):
            world.read_file("common/rule.txt")
        self.assertEqual(WorldSources(self.root).list_files()["total"], 0)
