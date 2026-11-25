"""Otwórz zakładkę kraju lub wskaż element interfejsu aktywnej kampanii."""

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Annotated, Any

from mcp_types import ToolAnnotations
from pydantic import Field

from campaign_ui_driver import GameInputError, SUPPORTED_UI_VERSIONS, _GameWindow, _hover_at, _point, _retry_pointer, _session


@dataclass(frozen=True)
class _Button:
    path: str
    sprite: str

    def matches(self, item):
        return (item.get("path") == self.path and item.get("type") == "button"
                and item.get("sprite") == self.sprite and item.get("enabled") is True)


SHIELD = _Button("topbar/player_shield", "GFX_shield_fancy")
TABS_PATH = "countryview/countryview_tabs"
GAME_MENU = "//menu_panel/menu_close_button"
CONFIRMATION = "//DefaultConfirm"

# countryview.gui and the corresponding country*view.gui files in EU4 1.37.5.
# Each entry gives the tab ID, its sprite, and the country panel that must appear.
TABS = {
    "court": ("court", "GFX_tab_court", "countrycourtview"),
    "government": ("gov", "GFX_tab_local_government", "countrygovernmentview"),
    "diplomacy": ("diplomacy", "GFX_tab_policies", "countrydiplomacyview"),
    "economy": ("economy", "GFX_tab_economy", "countryeconomyview"),
    "trade": ("trade", "GFX_tab_domestic_trade", "countrytradeview"),
    "technology": ("technology", "GFX_tab_domestic_technology", "countrytechnologyview"),
    "ideas": ("ideas", "GFX_tab_domestic_ideas", "countryideasview"),
    "missions": ("missions", "GFX_tab_domestic_mission", "countrymissionsview"),
    "decisions": ("decisions", "GFX_tab_decisions", "countrydecisionsview"),
    "stability": ("stability", "GFX_tab_domestic_government", "countrystabilityview"),
    "religion": ("religion", "GFX_tab_religion", "countryreligionview"),
    "military": ("military", "GFX_tab_military", "countrymilitaryview"),
    "subjects": ("subjects", "GFX_tab_subjects", "countrysubjectview"),
    "estates": ("estates", "GFX_tab_estates", "countryestatesview"),
}


async def _read(server, name, **arguments):
    result = await server.read_live(name, arguments)
    if result.get("available") is not True:
        raise GameInputError("live_unavailable", "Nie udało się odczytać otwartej gry. Spróbuj ponownie.")
    return result


def _in_game(state):
    if state.get("in_game") is not True:
        raise GameInputError("not_in_game", "Otwórz kampanię w EU4 i spróbuj ponownie.")
    return _session(state)


class _Navigation:
    def __init__(self, server, target, identity):
        self.server = server
        self.target = target
        self.identity = identity

    async def _guard(self):
        state = await _read(self.server, "tongs_state")
        if _in_game(state) != self.identity:
            raise GameInputError("session_changed", "Kampania zmieniła się podczas tej próby. Spróbuj ponownie.")

    async def _find(self, selector):
        result = await _read(self.server, "tongs_ui_find", selector=selector, limit=2)
        matches = result.get("matches")
        if result.get("count") == 0 and result.get("truncated") is False and matches == []:
            return None
        if (result.get("count") != 1 or result.get("truncated") is not False
                or not isinstance(matches, list) or len(matches) != 1 or not isinstance(matches[0], dict)):
            raise GameInputError("ambiguous_widget", "Gra nie wskazała dokładnie jednego elementu interfejsu.")
        item = matches[0]
        if (item.get("visible") is not True or item.get("stale") is True
                or not isinstance(item.get("path"), str) or not item["path"]):
            raise GameInputError("unexpected_ui", "Gra nie potwierdziła widoczności elementu interfejsu.")
        return item

    async def _guard_navigation(self):
        await self._guard()
        if await self._find(CONFIRMATION):
            raise GameInputError("confirmation_open", "Zamknij potwierdzenie w grze i spróbuj ponownie.")
        if await self._find(GAME_MENU):
            raise GameInputError("game_menu_open", "Zamknij menu gry i spróbuj ponownie.")

    async def _button(self, button):
        item = await self._find("//" + button.path)
        if item is not None and not button.matches(item):
            raise GameInputError("unexpected_ui", "Przycisk otwierający zakładkę jest niedostępny. Sprawdź ekran gry.")
        return item

    async def _panel(self, name):
        item = await self._find("//" + name)
        return item is not None and item.get("path") == name and item.get("type") == "window"

    async def _under_pointer(self, item, point):
        cursor = await _read(self.server, "tongs_cursor", timeout=1)
        if _session(cursor) != self.identity:
            raise GameInputError("session_changed", "Kampania zmieniła się przed użyciem wskaźnika.")
        return (cursor.get("pointer") == "mouse" and cursor.get("inside") is True
                and _point(cursor.get("point")) == point and cursor.get("widget") == item["path"])

    async def _hover(self, item):
        center = _point(item.get("click_point"))
        rect = item.get("rect")
        points = [] if center is None else [center]
        if isinstance(rect, dict) and _point(rect) is not None:
            x, y = _point(rect)
            width, height = rect.get("w"), rect.get("h")
            if type(width) is int and type(height) is int and width > 0 and height > 0:
                mid_y = y + height // 2
                edge = min(4, (width - 1) // 2)
                points.extend(((x + width // 2, mid_y), (x + edge, mid_y), (x + width - 1 - edge, mid_y)))
        if not points:
            raise GameInputError("widget_position_unavailable", "Gra nie podała położenia elementu na ekranie.")

        await self._guard()
        on_screen = (point for point in dict.fromkeys(points)
                     if 0 <= point[0] < self.target.size[0] and 0 <= point[1] < self.target.size[1])
        point = await _hover_at(self.target, on_screen, lambda xy: self._under_pointer(item, xy))
        if point is not None:
            return point
        raise GameInputError("widget_covered", "Element jest zasłonięty lub poza ekranem. Sprawdź ekran gry.")

    async def _click(self, button, item):
        async def click():
            point = await self._hover(item)
            await self._guard_navigation()
            current = await self._button(button)
            if current is None:
                raise GameInputError("widget_changed", "Przycisk zniknął z ekranu. Spróbuj ponownie.")
            if not await self._under_pointer(current, point):
                self.target.require_pointer(point)
                raise GameInputError("widget_changed", "Gra nie potwierdziła przycisku pod wskaźnikiem.")
            self.target.click(point)

        await _retry_pointer(click)

    async def _wait(self, check, message):
        end = monotonic() + 1.5
        while True:
            await self._guard()
            found = await check()
            if found:
                return found
            if monotonic() >= end:
                raise GameInputError("navigation_unconfirmed", message)
            await asyncio.sleep(0.075)

    async def open_tab(self, tab):
        widget_name, sprite, panel = TABS[tab]
        button = _Button(f"{TABS_PATH}/tab_{widget_name}", sprite)
        await self._guard_navigation()
        item = await self._button(button)
        if item is not None and await self._panel(panel):
            await self.target.focus()
            await self._guard_navigation()
            if not await self._panel(panel):
                raise GameInputError("navigation_unconfirmed", "Zakładka zniknęła. Spróbuj ponownie.")
            return {"opened": True, "already_open": True, "tab": tab, "panel": panel}

        await self.target.focus()
        if item is None:
            shield = await self._button(SHIELD)
            if shield is None:
                raise GameInputError("widget_not_visible", "Gra nie pokazuje tarczy kraju. Wróć do mapy i spróbuj ponownie.")
            await self._click(SHIELD, shield)
            item = await self._wait(lambda: self._button(button), "Nie udało się otworzyć panelu kraju.")
        if not await self._panel(panel):
            await self._click(button, item)
            await self._wait(lambda: self._panel(panel), "Gra nie potwierdziła otwarcia zakładki.")
        return {"opened": True, "already_open": False, "tab": tab, "panel": panel}

    async def point(self, selector):
        item = await self._find(selector)
        if item is None:
            raise GameInputError("widget_not_visible", "Element nie jest teraz widoczny. Otwórz właściwą zakładkę.")
        await self.target.focus()

        async def point_at_widget():
            point = await self._hover(item)
            self.target.leave_cursor(point)
            return point

        x, y = await _retry_pointer(point_at_widget)
        return {"pointed": True, "widget": item["path"], "point": {"x": x, "y": y},
                "text": item.get("text"), "enabled": item.get("enabled")}


async def _run(server, action, value):
    try:
        async with asyncio.timeout(15):
            check_input = server.ui_control.begin()
            identity = _in_game(await _read(server, "tongs_state"))
            window = await _read(server, "tongs_window")
            check_input()
            if not server.world.game_dir or server.world.version not in SUPPORTED_UI_VERSIONS:
                raise GameInputError("unsupported_game_version", "Przełączanie zakładek i wskazywanie wymaga EU4 1.37.5.")
            target = _GameWindow(server.world.game_dir / "eu4.exe", identity, window, check_input)
            with target.exclusive(), target:
                navigation = _Navigation(server, target, identity)
                result = await action(navigation, value)
                check_input()
                return result
    except GameInputError as exc:
        return {"error_code": exc.code, "error": str(exc)}
    except TimeoutError:
        return {"error_code": "input_timeout", "error": "Gra nie odpowiedziała na czas. Sprawdź ekran i spróbuj ponownie."}


def register_navigation(server):
    ui_actions = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=ui_actions)
    async def eu4_ui_resume() -> dict[str, Any]:
        """Przywróć sterowanie Lunie po F9. Użyj wyłącznie na wyraźną prośbę gracza o wznowienie. Nie porusza wskaźnikiem ani nie przełącza okna."""
        return server.ui_control.resume()

    @server.tool(annotations=ui_actions)
    async def eu4_ui_open_tab(
        tab: Annotated[str, Field(description="Nazwa zakładki kraju: " + ", ".join(TABS))],
    ) -> dict[str, Any]:
        """Otwiera wskazaną zakładkę kraju w EU4, w razie potrzeby zaczynając od tarczy na mapie. Potwierdza widoczność panelu."""
        if tab not in TABS:
            return {"error_code": "unknown_tab", "error": "Wybierz zakładkę kraju z listy.", "tabs": list(TABS)}
        return await _run(server, _Navigation.open_tab, tab)

    @server.tool(annotations=ui_actions)
    async def eu4_ui_point(
        selector: Annotated[str, Field(min_length=1, max_length=500, description="Selektor odczytu Tongs, np. //countryeconomyview/take_loan")],
    ) -> dict[str, Any]:
        """Ustawia wskaźnik na jednym widocznym elemencie znalezionym przez Tongs i pozostawia go tam. Wyłącznie ruch myszy, bez kliknięcia."""
        return await _run(server, _Navigation.point, selector)
