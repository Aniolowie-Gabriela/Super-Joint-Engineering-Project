import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

import campaign_compare
from saves import SaveProvider


class SaveCompareTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.second_root = self.root / "drugi-katalog"
        self.second_root.mkdir()
        self.server = MCPServer("save-compare-test")
        campaign_compare.register_save_compare(
            self.server, SaveProvider([self.root, self.second_root]), ToolAnnotations(read_only_hint=True),
        )

    def _write(self, name, *, player="POL", date="1444.11.11", campaign="campaign-a",
               fields="treasury=17.2 manpower=11.5 loan={ amount=24.6 }", wars="", mtime=10, root=None):
        path = (self.root if root is None else root) / name
        identity = f'campaign_id="{campaign}"' if campaign is not None else ""
        path.write_text(
            f'EU4txt\ndate={date} player={player} {identity}\n'
            f'countries={{ {player}={{ {fields} }} }}\n{wars}\n',
            encoding="utf-8",
        )
        os.utime(path, (mtime, mtime))
        return path

    async def _compare(self, **arguments):
        result = await self.server.call_tool("eu4_save_compare", arguments)
        self.assertFalse(result.is_error, result)
        return result.structured_content

    async def test_uses_latest_readable_later_save_of_same_campaign_and_reports_sources(self):
        initial = self._write("przed-wojna.eu4")
        later = self._write(
            "autosave.eu4", date="1445.1.2", fields="treasury=0 manpower=1.23", mtime=30,
            wars='active_war={ name="Wojna bałtycka" attackers={ LIT } defenders={ POL } }',
        )
        self._write("stary-autosave.eu4", date="1445.12.9", mtime=20)
        self._write("poprzedni.eu4", date="1444.11.8", mtime=40)
        self._write("inna-kampania.eu4", date="1445.12.9", campaign="campaign-b", mtime=50)
        self._write("bez-identyfikatora.eu4", date="1446.2.2", campaign=None, mtime=60)
        broken = self.root / "uszkodzony.eu4"
        broken.write_bytes(b"EU4txt\ndate=1445.1.3 player=POL campaign_id=campaign-a countries={")
        os.utime(broken, (70, 70))
        files_before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.glob("*.eu4")}

        result = await self._compare(before=initial.name)

        self.assertTrue(result["available"], result)
        self.assertEqual(result["selection"], "latest_later_save")
        self.assertEqual((result["before"]["save"], result["after"]["save"]), (initial.name, later.name))
        self.assertEqual((result["before"]["game_date"], result["after"]["game_date"]), ("1444.11.11", "1445.1.2"))
        for info in (result["before"], result["after"]):
            self.assertEqual(info["source"], "save")
            self.assertEqual(info["root_index"], 0)
            self.assertEqual(info["campaign_id"], "campaign-a")
            self.assertEqual(info["player"], "POL")
            self.assertEqual(info["format"], "text")
        self.assertEqual(result["changes"]["treasury_ducats"], {"before": 17.2, "after": 0.0, "delta": -17.2})
        self.assertEqual(result["changes"]["debt_ducats"], {"before": 24.6, "after": 0.0, "delta": -24.6})
        self.assertEqual(result["changes"]["manpower_thousands"]["delta"], -10.27)
        self.assertEqual(result["changes"]["max_manpower_thousands"], {"before": None, "after": None, "delta": None})
        self.assertEqual(result["changes"]["active_wars"], {"before": 0, "after": 1, "delta": 1})
        self.assertEqual(result["wars"]["after"]["examples"][0]["name"], "Wojna bałtycka")
        self.assertEqual({path.name for path in self.root.iterdir()}, {*files_before, self.second_root.name})
        self.assertEqual(
            {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.glob("*.eu4")}, files_before,
        )
        tool, = await self.server.list_tools()
        self.assertEqual(tool.name, "eu4_save_compare")
        self.assertTrue(tool.annotations.read_only_hint)

    async def test_explicit_compare_allows_the_same_date_but_rejects_reversed_unrelated_or_same_files(self):
        start = self._write("poczatek.eu4")
        self._write("ten-sam-dzien.eu4", fields="manpower=0")
        self._write("inna.eu4", campaign="campaign-b", date="1444.11.13")
        self._write("wczesniej.eu4", date="1444.11.10")

        args = {"before": start.name}
        self.assertEqual((await self._compare(**args))["error_code"], "later_save_not_found")
        invalid = {
            "inna.eu4": "different_campaign", "wczesniej.eu4": "earlier_save",
            start.name: "same_save", "nieistniejacy.eu4": "save_not_found", "../poczatek.eu4": "invalid_request",
        }
        for name, error_code in invalid.items():
            with self.subTest(name=name):
                self.assertEqual((await self._compare(after=name, **args))["error_code"], error_code)
        same_day = await self._compare(after="ten-sam-dzien.eu4", **args)
        self.assertTrue(same_day["same_game_date"])
        self.assertEqual(same_day["selection"], "named")
        self.assertEqual(same_day["changes"]["treasury_ducats"], {"before": 17.2, "after": None, "delta": None})

    async def test_no_campaign_id_refuses_to_infer_a_match_from_the_player_or_filename(self):
        initial = self._write("dawny.eu4", campaign=None)
        later = self._write("dawny-autosave.eu4", campaign=None, date="1445.1.2")
        modern = self._write("identyfikator.eu4", date="1444.11.12")
        blank = self._write("pusty-id.eu4", campaign=" ", date="1445.1.3")
        for before, after in ((initial, later), (initial, modern), (modern, later), (modern, blank)):
            with self.subTest(before=before.name, after=after.name):
                result = await self._compare(before=before.name, after=after.name)
                self.assertEqual(result["error_code"], "save_identity_unavailable")
        self.assertEqual((await self._compare(before=modern.name))["error_code"], "later_save_not_found")

    async def test_supports_old_luna_filename_without_a_marker_and_reads_zip_saves(self):
        initial = self._write("luna_wojna_" + "1" * 32 + ".eu4")
        later = self.root / "zmiana-kraju.eu4"
        with ZipFile(later, "w", ZIP_DEFLATED) as archive:
            archive.writestr("meta", 'EU4txt\ndate=1444.11.12 player=PLC campaign_id="campaign-a"')
            archive.writestr("gamestate", 'EU4txt\ncountries={ PLC={ treasury=20.2 } }')

        result = await self._compare(before=initial.name, after=later.name)

        self.assertTrue(result["available"], result)
        self.assertTrue(result["player_changed"])
        self.assertEqual(result["after"]["format"], "zip-text")
        self.assertEqual(result["after"]["player"], "PLC")
        self.assertEqual(result["changes"]["treasury_ducats"]["delta"], 3.0)

    async def test_duplicate_names_require_root_indexes_and_auto_mode_can_filter_roots(self):
        initial = self._write("zapis.eu4")
        self._write(initial.name, date="1444.11.12", root=self.second_root)
        self._write("autosave.eu4", date="1444.11.14", mtime=30)

        self.assertEqual((await self._compare(before=initial.name))["error_code"], "ambiguous_save")
        self.assertEqual(
            (await self._compare(before=initial.name, before_root_index=0, after=initial.name))["error_code"],
            "ambiguous_save",
        )
        for arguments in ({"after": initial.name}, {}):
            result = await self._compare(before=initial.name, before_root_index=0, after_root_index=1, **arguments)
            self.assertTrue(result["available"], result)
            self.assertEqual((result["before"]["root_index"], result["after"]["root_index"]), (0, 1))
            self.assertEqual(result["after"]["save"], initial.name)

    async def test_rejects_a_file_changed_during_comparison(self):
        initial = self._write("poczatek.eu4")
        later = self._write("pozniej.eu4", date="1444.11.12")
        load_after = campaign_compare._load_after

        def change_initial(*args, **kwargs):
            result = load_after(*args, **kwargs)
            with initial.open("ab") as handle:
                handle.write(b"\n# updated save\n")
            return result

        with patch.object(campaign_compare, "_load_after", side_effect=change_initial):
            result = await self._compare(before=initial.name, after=later.name)

        self.assertEqual(result["error_code"], "save_changing")
        self.assertNotIn("changes", result)


if __name__ == "__main__":
    unittest.main()
