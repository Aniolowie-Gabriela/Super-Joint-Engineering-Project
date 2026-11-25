from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock

from mcp_types import CallToolResult, Tool

from campaign_map import register_map
from saves import SaveProvider
from server import AdvisorServer, READ_ONLY


MAP_SAVE = """\
EU4txt
date=1444.12.8 player="ENG" campaign_id="tutorial"
provinces={
    -236={ name="London" owner="ENG" controller="ENG" }
    -373={ name="Pale" owner="ENG" controller="REB" }
    -242={ name="Glamorgan" owner="WAL" controller={ tag="ENG" } }
    -1284={ name="Irish Sea" }
    -378={ name="Cork" owner="ENG" }
}
countries={
    ENG={
        capital=236
        army={ name="Royal Army" location=236 regiment={} regiment={} }
        navy={ name="Royal Navy" location=1284 ship={} }
    }
}
"""
TOOLS = ("tongs_state", "tongs_selection", "tongs_province", "tongs_player", "tongs_country", "tongs_units")
LIVE_STATE = {"in_game": True, "date": "1444.12.9", "pid": 100, "process_start_ms": 1000, "session": 1}


class CampaignMapTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "tutorial.eu4"
        self.path.write_text(MAP_SAVE, encoding="utf-8")
        self.saves = Mock(wraps=SaveProvider([self.root]))
        self.world = Mock(call_live=AsyncMock())
        self.world.call_live.side_effect = lambda name, params: self.native({"in_game": False})
        tools = [Tool(name=name, input_schema={"type": "object"}, annotations=READ_ONLY) for name in TOOLS]
        self.server = AdvisorServer(self.world, tools)
        register_map(self.server, self.world, self.saves, READ_ONLY)

    def native(self, payload, *, error=False):
        return CallToolResult(content=[], structured_content=payload, is_error=error)

    async def call(self, name, **params):
        result = await self.server.call_tool(f"eu4_map_{name}", params)
        return result.structured_content

    def mock_live(self, **results):
        def reply(tool, params):
            value = results[tool.removeprefix("tongs_")]
            return self.native(value(params) if callable(value) else value)
        self.world.call_live.side_effect = reply

    async def test_open_panel_uses_live_owner_and_controller(self):
        self.mock_live(
            state=LIVE_STATE,
            selection={"last_selected": 236, "view": {"visible": True, "province": 373}},
            province={"name": "Pale", "owner": "ENG", "controller": "REB", "land": True},
        )
        result = await self.call("provinces")
        self.assertEqual(result["source"], "live")
        self.assertEqual(result["date"], "1444.12.9")
        self.assertEqual(result["panel"], {"visible": True, "province_id": 373})
        self.assertTrue(result["items"][0]["occupied"])
        self.assertEqual(result["items"][0]["controller"], "REB")
        self.assertEqual(result["visibility"], {"fog_of_war": "unknown", "on_screen": "unknown"})
        self.saves.snapshot.assert_not_called()

    async def test_closed_panel_ignores_last_selection(self):
        self.mock_live(state=LIVE_STATE, selection={"last_selected": 373, "view": {"visible": False, "province": 373}})
        result = await self.call("provinces")
        self.assertEqual(result["error_code"], "province_panel_closed")
        self.saves.snapshot.assert_not_called()

    async def test_live_read_repeats_after_save_reload(self):
        states = iter([LIVE_STATE, {**LIVE_STATE, "session": 2}, {**LIVE_STATE, "session": 2}])
        provinces = iter([
            {"owner": "ENG", "controller": "REB"},
            {"owner": "ENG", "controller": "ENG"},
        ])
        self.mock_live(state=lambda _: next(states), province=lambda _: next(provinces))
        result = await self.call("provinces", province_ids=[373])
        self.assertEqual(result["session"], 2)
        self.assertFalse(result["items"][0]["occupied"])

    async def test_live_occupation_page_covers_owned_provinces_only(self):
        provinces = {236: {"owner": "ENG", "controller": "ENG"}, 373: {"owner": "ENG", "controller": "REB"}}
        self.mock_live(state=LIVE_STATE, player={"tag": "ENG"}, country={"capital": 236, "provinces": [236, 373]},
                       province=lambda params: provinces[params["province_id"]])

        first = await self.call("occupations", direction="both", limit=1)
        self.assertEqual(first["items"], [])
        self.assertEqual(first["next_offset"], 1)
        self.assertEqual(first["page_by"], "owned_provinces")
        self.assertEqual(first["checked_provinces"], 1)
        self.assertTrue(first["outgoing_unavailable_live"])

        next_page = await self.call("occupations", offset=first["next_offset"], limit=1)
        self.assertEqual(next_page["items"][0]["direction"], "incoming")
        self.assertEqual(next_page["items"][0]["province_id"], 373)
        self.assertIsNone(next_page["next_offset"])

    async def test_live_global_query_needs_selected_save(self):
        self.mock_live(state=LIVE_STATE)
        result = await self.call("occupations", direction="outgoing")
        self.assertTrue(result["fallback_requires_save"])
        self.saves.snapshot.assert_not_called()

        result = await self.call("occupations", direction="outgoing", campaign_id="tutorial")
        self.assertEqual(result["source"], "save")
        self.assertEqual(result["save"], self.path.name)
        self.assertEqual(result["game_date"], "1444.12.8")
        self.assertEqual(result["live_campaign_match"], "unverified")
        self.assertEqual(result["items"][0]["province_id"], 242)
        self.assertEqual(result["items"][0]["direction"], "outgoing")

    async def test_explicit_save_reports_its_campaign_while_game_is_open(self):
        (self.root / "other.eu4").write_text(
            MAP_SAVE.replace('"tutorial"', '"other"').replace('controller="REB"', 'controller="ENG"'), encoding="utf-8",
        )
        self.mock_live(state=LIVE_STATE, province={"owner": "ENG", "controller": "REB"})
        result = await self.call("provinces", province_ids=[373], save="other.eu4")
        self.assertEqual(result["source"], "save")
        self.assertEqual(result["campaign_id"], "other")
        self.assertEqual(result["game_date"], "1444.12.8")
        self.assertFalse(result["items"][0]["occupied"])
        self.world.call_live.assert_not_awaited()

        without_scope = await self.call("provinces", save="other.eu4")
        self.assertEqual(without_scope["error_code"], "save_scope_required")

    async def test_world_paginates_one_snapshot_per_request(self):
        first = await self.call("provinces", scope="world", limit=2)
        self.assertEqual(first["total"], 5)
        self.assertEqual([p["province_id"] for p in first["items"]], [236, 373])
        self.saves.snapshot.assert_called_once()

        later = await self.call("provinces", scope="world", offset=first["next_offset"], limit=2)
        self.assertEqual(later["source"], "save")
        self.assertEqual([p["province_id"] for p in later["items"]], [242, 1284])
        self.assertIsNone(later["items"][1]["occupied"])

    async def test_root_index_selects_save_even_when_live_is_available(self):
        self.mock_live(state=LIVE_STATE, units={"tag": "ENG", "units": []})
        result = await self.call("units", root_index=0)
        self.assertEqual(result["source"], "save")
        self.assertEqual(result["root_index"], 0)
        self.assertEqual(result["campaign_id"], "tutorial")
        self.assertEqual(result["total"], 2)
        self.world.call_live.assert_not_awaited()

    async def test_installed_area_membership_does_not_use_color_numbers(self):
        self.world.read_file.return_value = {
            "game_version": "1.37.5",
            "next_line": None,
            "lines": [{"text": line, "truncated": False} for line in [
                "some_area = { # Ireland", "   color = { 1 2 3 }", "   373 378", "}",
            ]],
        }
        result = await self.call("provinces", area="some_area")
        self.assertEqual(result["area_definition"]["game_version"], "1.37.5")
        self.assertFalse(result["area_definition"]["campaign_membership_verified"])
        self.assertEqual([p["province_id"] for p in result["items"]], [373, 378])
        self.assertIsNone(result["items"][1]["occupied"])

    async def test_save_requires_choice_between_campaigns(self):
        (self.root / "other.eu4").write_text(MAP_SAVE.replace('"tutorial"', '"other"'), encoding="utf-8")
        result = await self.call("provinces", scope="world")
        self.assertEqual(result["error_code"], "selection_required")

    async def test_units_use_current_locations_or_save_province_names(self):
        saved = await self.call("units")
        self.assertEqual(saved["game_date"], "1444.12.8")
        self.assertEqual(saved["items"], [
            {"kind": "army", "name": "Royal Army", "location": 236, "subunits": 2, "province_name": "London"},
            {"kind": "navy", "name": "Royal Navy", "location": 1284, "subunits": 1, "province_name": "Irish Sea"},
        ])
        self.mock_live(state=LIVE_STATE, units={"tag": "ENG", "units": [
            {"kind": "army", "name": "Royal Army", "location": 373, "mission": "siege"},
            {"kind": "navy", "name": "Royal Navy", "location": 1284},
        ]}, province={"name": "Pale", "owner": "ENG", "controller": "REB"})
        live = await self.call("units", kind="army")
        self.assertEqual(live["source"], "live")
        self.assertEqual(live["total"], 1)
        self.assertEqual(live["items"][0]["province_name"], "Pale")
        self.assertEqual(live["items"][0]["mission"], "siege")


if __name__ == "__main__":
    unittest.main()
