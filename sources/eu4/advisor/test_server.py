import unittest
from unittest.mock import AsyncMock, Mock, patch

from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, Tool

from server import READ_ONLY, create_server
from campaign_ui_driver import GameInputError


class AdvisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        state = Tool(name="tongs_state", input_schema={"type": "object"}, annotations=READ_ONLY)
        self.world = Mock(live_tools=AsyncMock(return_value=[state]), call_live=AsyncMock())
        self.saves = Mock()
        self.server = await create_server(self.world, self.saves)

    async def test_active_campaign_wins_over_save(self):
        native = {"ok": True, "in_game": True, "date": "1530.4.4", "session": 2, "pid": 1024}
        self.world.call_live.return_value = CallToolResult(content=[], structured_content=native)

        answer = await self.server.call_tool("eu4_campaign_state", {})

        self.assertEqual(answer.structured_content["source"], "live")
        self.assertEqual(answer.structured_content["date"], "1530.4.4")
        self.assertEqual(answer.structured_content["session"], 2)
        self.saves.status.assert_not_called()

    async def test_unavailable_live_uses_the_available_save(self):
        self.world.call_live.side_effect = ToolError("Brak połączenia z grą.")
        self.saves.status.return_value = {
            "source": "save", "campaign_id": "campaign-a", "game_date": "1530.4.2", "available": True,
            "save": "older.eu4", "root_index": 0,
        }

        answer = await self.server.call_tool("eu4_campaign_state", {})

        self.saves.status.assert_called_once_with(None, root_index=None, campaign_id=None, require_campaign=True)
        self.assertEqual(answer.structured_content["game_date"], "1530.4.2")
        self.assertEqual(answer.structured_content["source"], "save")
        self.assertEqual(answer.structured_content["live_campaign_match"], "unverified")
        self.assertFalse(answer.structured_content["live"]["available"])
        wars = answer.structured_content["follow_up"]["active_wars"]
        self.assertEqual(wars["tool"], "eu4_country_briefing")
        self.assertEqual(wars["arguments"], {"save": "older.eu4", "root_index": 0})

    async def test_explicit_selection_reads_save_even_when_live_is_available(self):
        native = {"ok": True, "in_game": True, "date": "1530.4.4"}
        self.world.call_live.return_value = CallToolResult(content=[], structured_content=native)
        self.saves.status.return_value = {"source": "save", "available": True, "game_date": "1530.4.2"}

        for args in ({"campaign_id": "campaign-a"}, {"save": "older.eu4"}, {"root_index": 0}):
            with self.subTest(args=args):
                answer = await self.server.call_tool("eu4_campaign_state", args)
                self.assertEqual(answer.structured_content["source"], "save")
                self.saves.status.assert_called_with(args.get("save"), campaign_id=args.get("campaign_id"),
                                                    root_index=args.get("root_index"), require_campaign=True)
        self.world.call_live.assert_not_awaited()

    async def test_menu_and_ambiguous_campaign_are_distinct(self):
        self.world.call_live.return_value = CallToolResult(content=[], structured_content={"ok": True, "in_game": False})
        self.saves.status.return_value = {"source": "save", "available": False, "error_code": "selection_required"}

        answer = await self.server.call_tool("eu4_campaign_state", {})

        self.assertEqual(answer.structured_content["error_code"], "selection_required")
        self.assertTrue(answer.structured_content["live"]["available"])
        self.assertFalse(answer.structured_content["live"]["in_game"])

    async def test_missing_tongs_adapter_keeps_the_save_fallback(self):
        self.world.live_tools.return_value = []
        self.saves.status.return_value = {"source": "save", "available": True, "game_date": "1500.1.1"}
        server = await create_server(self.world, self.saves)

        answer = await server.call_tool("eu4_campaign_state", {})

        self.assertTrue(answer.structured_content["available"])
        self.assertEqual(answer.structured_content["live"]["error_code"], "live_tool_unavailable")
        self.world.call_live.assert_not_awaited()

    async def test_unsupported_live_tool_is_never_forwarded(self):
        listed = {tool.name: tool for tool in await self.server.list_tools()}
        self.assertEqual(listed["tongs_state"].input_schema, {"type": "object"})
        writes = {name for name, tool in listed.items() if not tool.annotations.read_only_hint}
        self.assertEqual(writes, {"eu4_ui_open_tab", "eu4_ui_point", "eu4_ui_resume"})
        self.assertTrue(listed["eu4_save_compare"].annotations.read_only_hint)
        for name in ("tongs_raw", "tongs_ui_click", "tongs_click_point", "eu4_checkpoint_create", "tongs_screenshot"):
            with self.subTest(name=name), self.assertRaises(ToolError):
                await self.server.call_tool(name, {})
        self.world.call_live.assert_not_awaited()


    async def test_f9_pauses_navigation_and_keeps_reads_available(self):
        self.server.ui_control.begin = Mock(side_effect=GameInputError("ui_control_paused", "F9"))
        for name, args in (("eu4_ui_open_tab", {"tab": "economy"}), ("eu4_ui_point", {"selector": "//foo"})):
            with self.subTest(tool=name):
                result = await self.server.call_tool(name, args)
                self.assertEqual(result.structured_content["error_code"], "ui_control_paused")
        self.world.call_live.assert_not_awaited()
        self.world.call_live.return_value = CallToolResult(content=[], structured_content={"ok": True})
        self.assertTrue((await self.server.call_tool("tongs_state", {})).structured_content["available"])

    async def test_screenshot_returns_image_block_after_handover(self):
        self.server.ui_control.begin = Mock(side_effect=AssertionError("screenshots must not request control"))
        with patch("campaign_screenshot.capture_frame", return_value=b"\xff\xd8\xff\xd9") as capture:
            result = await self.server.call_tool("eu4_ui_screenshot", {})
        capture.assert_called_once_with(self.world.game_dir)
        image, = result.content
        self.assertEqual((image.type, image.mime_type, image.data), ("image", "image/jpeg", "/9j/2Q=="))
        self.assertFalse(result.is_error)


if __name__ == "__main__":
    unittest.main()
