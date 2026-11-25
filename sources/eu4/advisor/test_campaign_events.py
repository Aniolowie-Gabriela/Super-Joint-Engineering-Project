import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from campaign_events import register_events
from saves import SaveProvider
from world import WorldSources


class CampaignEventsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        settings = {"gameId": "eu4", "rawVersion": "1.37.5.0"}
        (self.root / "launcher-settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (self.root / "events").mkdir()
        self.server = MCPServer("campaign-events-test")
        self.server.read_live = AsyncMock()
        register_events(self.server, WorldSources(self.root), SaveProvider([self.root]),
                        ToolAnnotations(read_only_hint=True))

    def _live(self, **data):
        state = {"available": True, "in_game": True, "pid": 1, "session": 2, "date": "1444.11.12"}
        responses = {
            "tongs_state": state, "tongs_player": {"available": True, "tag": "POL"},
            "tongs_event_list": {"available": True, "events": []},
            "tongs_country": {"available": True, "pending_events": []},
            **data,
        }
        self.server.read_live.side_effect = lambda name, _: responses[name]

    def _write_save(self, section, *, name="campaign.eu4", campaign_id="example"):
        (self.root / name).write_text(
            f"EU4txt\ndate=1444.11.11\nplayer=POL\ncampaign_id={campaign_id}\n{section}",
            encoding="utf-8",
        )

    async def _call(self, tool, **arguments):
        result = await self.server.call_tool(tool, arguments)
        self.assertFalse(result.is_error)
        return result.structured_content

    async def test_active_and_queued_keep_distinct_sources_and_instance_ids(self):
        windows = [{"id": "flavor_pol.18", "pending_id": 4,
                    "options": [{"option_key": "flavor_pol.18.a", "enabled": True}]}]
        events = [{"key": "flavor_pol.18", "pending_id": 5}, {"key": "flavor_pol.18", "pending_id": 4}]
        self._live(tongs_event_list={"available": True, "events": windows},
                   tongs_country={"available": True, "pending_events": events})

        first = await self._call("eu4_campaign_events", limit=1)
        second = await self._call("eu4_campaign_events", limit=1, offset=1)

        self.assertEqual(first["active"]["items"], windows)
        self.assertEqual(first["queued"]["items"], events[:1])
        self.assertEqual(first["queued"]["next_offset"], 1)
        self.assertEqual(second["queued"]["items"], events[1:])
        self.assertNotIn("saved_queued", first)
        self.server.read_live.assert_any_await("tongs_country", {"tag": "POL"})

    async def test_explicit_save_reads_only_that_campaign_even_when_live_has_its_own_events(self):
        self._live(tongs_event_list={"available": True, "events": [{"id": "live.1"}]},
                   tongs_country={"available": True, "pending_events": [{"key": "live.1"}]})
        self._write_save("""
        pending_events={
            event={event="flavor_pol.18" scope={country=POL}}
            event={event="flavor_pol.18" scope={country=POL}}
            event={event=1021 scope={country=LIT}}
            event={event=1022 scope={province=12 from={country=POL}}}
        }
        """)
        self._write_save("pending_events={ event={event=1023 scope={country=POL}} }",
                         name="other.eu4", campaign_id="other")

        answer = await self._call("eu4_campaign_events", campaign_id="example", limit=1, offset=1)

        self.server.read_live.assert_not_awaited()
        self.assertEqual(answer["active"]["error_code"], "event_windows_not_recorded")
        saved = answer["queued"]
        self.assertEqual((saved["source"], saved["save"], saved["game_date"]), ("save", "campaign.eu4", "1444.11.11"))
        self.assertEqual(saved["live_campaign_match"], "unverified")
        self.assertEqual(saved["unresolved_entries"], 1)
        self.assertEqual(saved["total"], 2)
        self.assertEqual(saved["items"][0], {
            "id": "flavor_pol.18", "path": ["pending_events", {"key": "event", "occurrence": 1}],
        })

    async def test_missing_live_queue_does_not_join_an_unverified_save_to_open_campaign(self):
        self._live(tongs_country={"available": True, "pending_events": None, "missing": {"pending_events": "unknown"}})
        self._write_save("pending_events={ event={event=1021 scope={country=POL}} }")

        answer = await self._call("eu4_campaign_events")

        self.assertEqual(answer["active"]["items"], [])
        self.assertFalse(answer["queued"]["available"])
        self.assertNotIn("saved_queued", answer)

    async def test_save_distinguishes_empty_and_missing_sections(self):
        self._live(tongs_state={"available": False})
        self._write_save("fired_events={ flavor_pol.18 }")
        missing = await self._call("eu4_campaign_events")
        self._write_save("pending_events={}")
        empty = await self._call("eu4_campaign_events")

        self.assertFalse(missing["active"]["available"])
        self.assertFalse(missing["saved_queued"]["available"])
        self.assertEqual(missing["saved_queued"]["error_code"], "missing_path")
        self.assertTrue(empty["saved_queued"]["available"])
        self.assertEqual(empty["saved_queued"]["items"], [])

    async def test_game_reload_during_read_invalidates_aggregated_state(self):
        state = {"available": True, "in_game": True, "pid": 1, "session": 1}
        self.server.read_live.side_effect = [
            state, {"available": True, "events": [{"id": "flavor_pol.18"}]},
            {"available": True, "tag": "POL"}, {"available": True, "pending_events": []},
            {**state, "session": 2},
        ]

        answer = await self._call("eu4_campaign_events")

        self.assertEqual(answer["active"]["error_code"], "live_session_changed")
        self.assertEqual(answer["queued"]["error_code"], "live_session_changed")

    async def test_event_definition_matches_top_level_id_and_keeps_ordered_option_blocks(self):
        (self.root / "events/flavor.txt").write_text("""namespace = flavor
country_event = { id = flavor.10 immediate = { country_event = { id = flavor.1 } } }
# country_event = { id = flavor.1 }
province_event =
{ "id" # ID can be followed by a comment
    = "flavor.1" is_triggered_only = yes
    trigger = { tag = POL }
    mean_time_to_happen = { months = 12 modifier = { factor = 0.1 is_year = 1447 } }
    immediate = { set_country_flag = began }
    option = { name = same add_treasury = 20 }
    option = {
        name = same # braces in a comment { }
        define_ruler = { name = "Zofia } #" }
    }
}
province_event = { id = 1021 title = EVTNAME1021 }
""", encoding="utf-8")

        definition = await self._call("eu4_event_definition", event_id="flavor.1", limit=1)
        option = await self._call("eu4_event_definition", event_id="flavor.1", path=definition["path"],
                                  section="option", occurrence=1, offset=2)
        numeric = await self._call("eu4_event_definition", event_id="1021")

        self.assertEqual((definition["kind"], definition["start_line"], definition["end_line"]), ("province_event", 4, 15))
        self.assertEqual(definition["properties"]["is_triggered_only"], "yes")
        self.assertEqual(definition["next_offset"], 1)
        self.assertEqual([section["key"] for section in definition["sections"]], [
            "trigger", "mean_time_to_happen", "immediate", "option", "option",
        ])
        self.assertEqual(option["lines"][0], {"line": 13, "text": '        define_ruler = { name = "Zofia } #" }',
                                             "truncated": False})
        self.assertEqual(numeric["properties"]["title"], "EVTNAME1021")


if __name__ == "__main__":
    unittest.main()
