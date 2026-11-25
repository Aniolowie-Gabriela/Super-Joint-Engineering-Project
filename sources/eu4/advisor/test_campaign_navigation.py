import unittest
from contextlib import nullcontext
from unittest.mock import AsyncMock, Mock

from campaign_navigation import CONFIRMATION, GAME_MENU, SHIELD, TABS_PATH, _Navigation, register_navigation
from campaign_ui_driver import GameInputError, _GameWindow


SESSION = {"pid": 123, "process_start_ms": 789, "session": 1}
ECONOMY_TAB = f"{TABS_PATH}/tab_economy"
ECONOMY_PANEL = "countryeconomyview"
LOAN = "countryeconomyview/take_loan"


class Screen:
    size = 500, 400

    def __init__(self, *, tab=None, modal=None, cover=None, enabled=True):
        self.tab = tab
        self.modal = modal
        self.cover = cover
        self.enabled = enabled
        self.clicks = []
        self.moves = []
        self.held = None
        self.pointer = None
        self.move_after_read = None
        self.focus = AsyncMock()

    def _widget(self, path):
        if self.modal and path == self.modal:
            return {"path": path[2:], "type": "window", "visible": True}
        if path == SHIELD.path:
            index, sprite = 10, SHIELD.sprite
        elif path == ECONOMY_TAB and self.tab is not None:
            index, sprite = 50, "GFX_tab_economy"
        elif path == LOAN and self.tab == "economy":
            index, sprite = 100, "GFX_take_loan_button"
        elif path == ECONOMY_PANEL and self.tab == "economy":
            return {"path": path, "type": "window", "visible": True}
        else:
            return None
        return {"path": path, "type": "button", "visible": True, "sprite": sprite,
                "enabled": self.enabled if path == LOAN else True,
                "click_point": {"x": index, "y": 20}}

    async def read_live(self, tool, arguments):
        if tool == "tongs_state":
            data = {"in_game": True, **SESSION}
        elif tool == "tongs_cursor":
            widget = {10: SHIELD.path, 50: ECONOMY_TAB, 100: LOAN}.get(self.pointer[0])
            data = {"pointer": "mouse", "inside": True, "point": dict(zip(("x", "y"), self.pointer)),
                    "widget": "some_menu" if widget == self.cover else widget, **SESSION}
            if widget == self.move_after_read:
                self.pointer = (200, 120)
                self.move_after_read = None
        elif tool == "tongs_ui_find":
            selector = arguments["selector"]
            if selector == "//*":
                return {"available": True, "count": 2, "matches": [{}, {}], "truncated": True}
            widget = self._widget(selector if selector == self.modal else selector[2:])
            data = {"count": int(widget is not None), "matches": [widget] if widget else [], "truncated": False}
        else:
            raise AssertionError(tool)
        return {"available": True, **data}

    def move(self, point):
        self.moves.append(point)
        self.pointer = point

    def click(self, point):
        self.require_pointer(point)
        self.clicks.append(point)
        if point == (10, 20):
            self.tab = "court"
        elif point == (50, 20):
            self.tab = "economy"
        else:
            raise AssertionError("Kliknięto poza przyciskami nawigacji.")

    def leave_cursor(self, point):
        self.require_pointer(point)
        self.held = point

    def pointer_at(self, point):
        return self.pointer == point

    def require_pointer(self, point):
        if not self.pointer_at(point):
            raise GameInputError("pointer_moved", "Wskaźnik przesunięty przez gracza.")


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    def navigation(self, **options):
        screen = Screen(**options)
        return _Navigation(screen, screen, tuple(SESSION.values())), screen

    async def test_opens_country_then_economy(self):
        navigation, screen = self.navigation()
        result = await navigation.open_tab("economy")
        self.assertEqual(result, {"opened": True, "already_open": False, "tab": "economy", "panel": ECONOMY_PANEL})
        self.assertEqual(screen.clicks, [(10, 20), (50, 20)])

    async def test_changes_tab_without_toggling_country_interface(self):
        navigation, screen = self.navigation(tab="court")
        await navigation.open_tab("economy")
        self.assertEqual(screen.clicks, [(50, 20)])

    async def test_leaves_open_tab_alone(self):
        navigation, screen = self.navigation(tab="economy")
        result = await navigation.open_tab("economy")
        self.assertTrue(result["already_open"])
        screen.focus.assert_awaited_once()
        self.assertEqual(screen.clicks, [])
        self.assertEqual(screen.moves, [])

    async def test_points_at_disabled_loan_without_clicking(self):
        navigation, screen = self.navigation(tab="economy", enabled=False)
        result = await navigation.point("//" + LOAN)
        self.assertEqual(result["widget"], LOAN)
        self.assertFalse(result["enabled"])
        self.assertEqual(screen.held, (100, 20))
        self.assertEqual(screen.clicks, [])

    async def test_mouse_motion_after_hover_repositions_before_pointing(self):
        navigation, screen = self.navigation(tab="economy")
        screen.move_after_read = LOAN

        result = await navigation.point("//" + LOAN)

        self.assertTrue(result["pointed"])
        self.assertEqual(screen.moves, [(100, 20), (100, 20)])
        self.assertEqual(screen.held, (100, 20))
        self.assertEqual(screen.clicks, [])

    async def test_mouse_motion_after_hover_requires_a_fresh_confirmation_before_click(self):
        navigation, screen = self.navigation(tab="court")
        screen.move_after_read = ECONOMY_TAB

        result = await navigation.open_tab("economy")

        self.assertTrue(result["opened"])
        self.assertEqual(screen.moves, [(50, 20), (50, 20)])
        self.assertEqual(screen.clicks, [(50, 20)])

    async def test_does_not_move_for_hidden_or_ambiguous_widget(self):
        navigation, screen = self.navigation()
        for selector, code in (("//" + LOAN, "widget_not_visible"), ("//*", "ambiguous_widget")):
            with self.subTest(selector=selector), self.assertRaises(GameInputError) as failure:
                await navigation.point(selector)
            self.assertEqual(failure.exception.code, code)
        self.assertEqual(screen.moves, [])
        self.assertEqual(screen.clicks, [])

    async def test_does_not_click_if_another_widget_covers_tab(self):
        navigation, screen = self.navigation(tab="court", cover=ECONOMY_TAB)
        with self.assertRaises(GameInputError) as failure:
            await navigation.open_tab("economy")
        self.assertEqual(failure.exception.code, "widget_covered")
        self.assertEqual(screen.clicks, [])

    async def test_does_not_dismiss_game_menu_or_confirmation(self):
        for selector, code in ((GAME_MENU, "game_menu_open"), (CONFIRMATION, "confirmation_open")):
            navigation, screen = self.navigation(modal=selector)
            with self.subTest(selector=selector), self.assertRaises(GameInputError) as failure:
                await navigation.open_tab("economy")
            self.assertEqual(failure.exception.code, code)
            self.assertEqual(screen.moves, [])
            self.assertEqual(screen.clicks, [])

    async def test_action_selector_is_not_a_tab(self):
        tools = {}

        class Server:
            read_live = AsyncMock()

            def tool(self, *, annotations):
                def add(function):
                    tools[function.__name__] = function
                    return function
                return add

        server = Server()
        register_navigation(server)
        result = await tools["eu4_ui_open_tab"]("//" + LOAN)
        self.assertEqual(result["error_code"], "unknown_tab")
        server.read_live.assert_not_awaited()

    def test_cursor_is_not_restored_while_player_holds_mouse(self):
        target = _GameWindow.__new__(_GameWindow)
        target.origin = (10, 20)
        target.expected_cursor = (50, 20)
        target.hwnd = 101
        target.process = 102
        target.restore_safe = True
        target.check_input = Mock()
        target._physical_dpi = nullcontext
        target._foreground = lambda: target.hwnd
        target._belongs_to_game = lambda _: True
        target._key_state = lambda key: -1 if key == 0x01 else 0
        target._read_cursor = lambda: target.expected_cursor
        target._at_game = lambda _: True
        target._set_cursor = Mock()
        target._close_handle = Mock()

        target.__exit__()

        target._set_cursor.assert_not_called()
        target._close_handle.assert_called_once_with(target.process)
