import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from mcp_types import CallToolResult, Tool

from country_briefing import register_briefing
from saves import SaveProvider
from server import AdvisorServer, READ_ONLY


class CountryBriefingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.saves = SaveProvider([Path(folder)])
        self.save = Path(folder, "campaign.eu4")
        self.save.write_text(
            """EU4txt
            date=1492.2.6 player=CAS campaign_id=test-campaign
            countries={
                CAS={ treasury=40 }
                POL={
                    capital=262 treasury=0 manpower=1.5 max_manpower=10 owned_provinces={ 262 }
                    ledger={ lastmonthincome=3.481 lastmonthexpense=5.481 }
                    loan={ amount=25 interest=4 expiry_date=1493.2.1 }
                    loan={ amount=20 interest=1 expiry_date=1494.1.1 }
                    army={ name="Army" location=262 regiment={ type=infantry } }
                }
            }
            diplomacy={
                dependency={ first=POL second=LIT subject_type=personal_union }
                dependency={ first=POL second=DAN end_date=1491.10.1 }
                alliance={ first=POL second=MOL }
            }
            active_war={
                name="Muscovite war" attackers={ MOS } defenders={ POL LIT }
                take_province={ type=take_claim casus_belli=cb_conquest province=280 }
            }
            active_war={ name="Incomplete war" attackers={ TUR } }
            previous_war={ name="Past war" attackers={ POL } defenders={ CZE } }
            """,
            encoding="utf-8",
        )
        self.world = Mock(call_live=AsyncMock(side_effect=self.native))
        self.live_available = False
        self.country_diplomacy = {
            "alliance": [], "subjects": [], "rivals": None, "overlord": None,
        }
        self.session = 1
        self.change_session = False
        tools = [
            Tool(name=f"tongs_{name}", input_schema={"type": "object"}, annotations=READ_ONLY)
            for name in ("state", "player", "country", "units", "ui_find")
        ]
        self.server = AdvisorServer(self.world, tools)
        register_briefing(self.server, self.world, self.saves, READ_ONLY)

    async def native(self, name, arguments):
        identity = {"session": self.session, "pid": 1024, "process_start_ms": 100}
        if name == "tongs_state":
            payload = {**identity, "in_game": self.live_available, "date": "1492.3.4"}
        elif name == "tongs_player":
            payload = {**identity, "tag": "CAS", "player_tag": "CAS", "observer": False}
        elif name == "tongs_country":
            if self.change_session:
                self.session += 1
            payload = {**identity, "tag": arguments["tag"], "exists": True,
                       "diplomacy": self.country_diplomacy}
        elif name == "tongs_units":
            payload = {"tag": arguments["tag"], "units": [
                {"kind": "army", "name": "Castile", "location": 219, "mission": "siege", "subunits": 10},
            ]}
        else:
            payload = {"count": 1, "matches": [
                {"visible": arguments["selector"].endswith("text_gold"), "text": "39,9"}
            ]}
        return CallToolResult(content=[], structured_content=payload)

    async def briefing(self, **arguments):
        result = await self.server.call_tool("eu4_country_briefing", arguments)
        self.assertFalse(result.is_error)
        return result.structured_content

    async def test_save_reports_other_countrys_war_and_budget(self):
        answer = await self.briefing(tag="pol", save=self.save.name)

        self.assertEqual(answer["source"], "save")
        self.assertEqual(answer["tag"], "POL")
        self.assertEqual(answer["player"], "CAS")
        self.assertEqual(answer["game_date"], "1492.2.6")
        self.assertEqual(answer["resources"]["treasury"], 0)
        self.assertIsNone(answer["resources"]["sailors"])
        self.assertEqual(answer["budget"]["last_month_balance"], -2)
        self.assertEqual(answer["budget"]["loans"]["principal"], 45)
        self.assertEqual(answer["diplomacy"]["subjects"]["examples"], ["LIT"])
        self.assertEqual(answer["military"]["army"]["regiments"], 1)
        self.assertEqual(answer["military"]["navy"]["ships"], 0)
        self.assertEqual(answer["wars"]["count"], 1)
        self.assertEqual(answer["wars"]["unclassified"], 1)
        war = answer["wars"]["examples"][0]
        self.assertEqual(war["side"], "defender")
        self.assertEqual(war["goal"]["casus_belli"], "cb_conquest")
        read = self.saves.read([*war["path"], "name"], save=self.save.name)
        self.assertEqual(read["value"], war["name"])
        self.assertEqual([item["topic"] for item in answer["attention"]],
                         ["active_wars", "last_month_deficit", "loans", "low_manpower"])

    async def test_live_reads_only_visible_player_resources(self):
        self.live_available = True
        answer = await self.briefing()

        self.assertEqual(answer["source"], "live")
        self.assertEqual(answer["diplomacy"]["subjects"]["examples"], [])
        self.assertIsNone(answer["diplomacy"]["rivals"])
        self.assertEqual(answer["resources_displayed"]["treasury"], "39,9")
        self.assertIsNone(answer["resources_displayed"]["stability"])
        self.assertEqual(answer["military"]["army"]["regiments"], 10)
        self.assertIsNone(answer["wars"])

        self.world.call_live.reset_mock()
        opponent = await self.briefing(tag="pol")

        self.assertTrue(all(name != "tongs_ui_find" for (name, _), _ in self.world.call_live.await_args_list))
        self.assertIsNone(opponent["resources_displayed"]["treasury"])

        self.world.call_live.reset_mock()
        saved = await self.briefing(tag="pol", save=self.save.name)
        self.world.call_live.assert_not_awaited()
        self.assertEqual(saved["live_campaign_match"], "unverified")
        self.assertEqual(saved["tag"], "POL")

    async def test_live_session_change_does_not_publish_inconsistent_data(self):
        self.live_available = True
        self.change_session = True
        answer = await self.briefing()

        self.assertEqual(answer["source"], "live")
        self.assertFalse(answer["available"])
        self.assertEqual(answer["error_code"], "live_session_changed")
        self.assertNotIn("resources", answer)
