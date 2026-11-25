"""Guarded Windows UI input for the EU4 advisor."""

import asyncio
import ctypes
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
import sys
from time import monotonic


SUPPORTED_UI_VERSIONS = frozenset({"1.37.5", "1.37.5.0", "1.37.5.2"})
SESSION_KEYS = ("pid", "process_start_ms", "session")
HANDOVER_KEY = "F9"


class GameInputError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.click_may_have_landed = False


class InputControl:
    """One Windows hotkey and one handover state for the lifetime of this MCP."""

    _HOTKEY_ID = 1
    _WM_HOTKEY = 0x0312

    def __init__(self):
        self._registered = False
        self._generation = 0
        self._paused = False

    def _register(self):
        if sys.platform != "win32":
            raise GameInputError("unsupported_platform", "Obsługa okna gry jest dostępna w systemie Windows.")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        register = _bind(user32, "RegisterHotKey", wintypes.BOOL, wintypes.HWND, ctypes.c_int,
                         wintypes.UINT, wintypes.UINT)
        self._unregister = _bind(user32, "UnregisterHotKey", wintypes.BOOL, wintypes.HWND, ctypes.c_int)
        self._peek = _bind(user32, "PeekMessageW", wintypes.BOOL, ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                           wintypes.UINT, wintypes.UINT, wintypes.UINT)
        if not register(None, self._HOTKEY_ID, 0x4000, 0x78):  # MOD_NOREPEAT, VK_F9
            if ctypes.get_last_error() == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                raise GameInputError("ui_hotkey_conflict", "F9 jest zajęty, np. przez inną sesję doradcy. Zwolnij F9 i ponów polecenie.")
            raise GameInputError("ui_hotkey_unavailable", "Windows nie udostępnił klawisza F9. Ponów polecenie.")
        self._registered = True

    def _drain(self):
        # Windows keeps the message even after a short press has ended. All control methods run on
        # the MCP thread, and this only removes that thread's WM_HOTKEY messages.
        if self._registered:
            message = wintypes.MSG()
            while self._peek(ctypes.byref(message), -1, self._WM_HOTKEY, self._WM_HOTKEY, 1):
                if message.wParam == self._HOTKEY_ID:
                    self._generation += 1
                    self._paused = True

    def _check(self, generation):
        self._drain()
        if self._paused:
            raise GameInputError("ui_control_paused", "Po naciśnięciu F9 sterujesz samodzielnie. Poproś Lunę o wznowienie, kiedy będzie potrzebne.")
        if generation != self._generation:
            raise GameInputError("ui_control_interrupted", "F9 przerwał to polecenie. Jeśli nadal go potrzebujesz, poproś ponownie.")

    def begin(self):
        if not self._registered:
            self._register()
        generation = self._generation
        self._check(generation)
        return lambda: self._check(generation)

    def resume(self):
        self._drain()
        resumed = self._paused
        self._paused = False
        return {"resumed": resumed, "paused": False, "handover_key": HANDOVER_KEY}

    def close(self):
        if self._registered:
            self._unregister(None, self._HOTKEY_ID)
            self._registered = False


async def _retry_pointer(action):
    # Each tool supplies a deadline for the entire operation, including these retries.
    while True:
        try:
            return await action()
        except GameInputError as exc:
            if exc.code != "pointer_moved":
                raise
        await asyncio.sleep(0.04)


def _pointer_moved():
    return GameInputError("pointer_moved", "Wskaźnik wciąż się przesuwa. Zatrzymaj go na chwilę i ponów polecenie.")


async def _hover_at(target, points, confirm):
    displaced = False
    for point in points:
        target.move(point)
        for attempt in range(3):
            if not target.pointer_at(point):
                displaced = True
                target.move(point)
            if await confirm(point):
                return point
            if attempt < 2:
                await asyncio.sleep(0.04)
        if not target.pointer_at(point):
            displaced = True
    if displaced:
        raise _pointer_moved()
    return None


def _session(state):
    identity = tuple(state.get(key) for key in SESSION_KEYS)
    if any(type(value) is not int or value <= 0 for value in identity):
        raise GameInputError("session_unavailable", "EU4 nie potwierdziło tożsamości otwartej kampanii.")
    return identity


def _point(value):
    if isinstance(value, dict) and all(type(value.get(key)) is int for key in ("x", "y")):
        return value["x"], value["y"]
    return None


def _bind(library, name, result_type, *argument_types):
    fn = getattr(library, name)
    fn.restype = result_type
    fn.argtypes = argument_types
    return fn


class _GameWindow:
    def __init__(self, exe, identity, window, check_input):
        if sys.platform != "win32":
            raise GameInputError("unsupported_platform", "Obsługa menu gry jest dostępna w systemie Windows.")
        self.exe = exe
        self.pid, self.process_start_ms, _ = identity
        self.thread = window.get("thread_id")
        self.size = window.get("width"), window.get("height")
        if window.get("minimized") is not False:
            raise GameInputError("game_minimized", "Przywróć okno EU4 i spróbuj ponownie.")
        if any(type(value) is not int or value <= 0 for value in (self.thread, *self.size)):
            raise GameInputError("window_unavailable", "Gra nie potwierdziła swojego okna. Spróbuj ponownie.")
        self.origin = self.expected_cursor = None
        self.restore_safe = True
        self.check_input = check_input
        self._load_win32()

    def _load_win32(self):
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        hwnd, point, boolean = wintypes.HWND, wintypes.POINT, wintypes.BOOL
        dword, handle, uint = wintypes.DWORD, wintypes.HANDLE, wintypes.UINT
        self._callback = ctypes.WINFUNCTYPE(boolean, hwnd, wintypes.LPARAM)
        self._enum_windows = _bind(u, "EnumWindows", boolean, self._callback, wintypes.LPARAM)
        self._foreground = _bind(u, "GetForegroundWindow", hwnd)
        self._set_foreground = _bind(u, "SetForegroundWindow", boolean, hwnd)
        self._thread_pid = _bind(u, "GetWindowThreadProcessId", dword, hwnd, ctypes.POINTER(dword))
        self._visible = _bind(u, "IsWindowVisible", boolean, hwnd)
        self._iconic = _bind(u, "IsIconic", boolean, hwnd)
        self._ancestor = _bind(u, "GetAncestor", hwnd, hwnd, uint)
        self._client_rect = _bind(u, "GetClientRect", boolean, hwnd, ctypes.POINTER(wintypes.RECT))
        self._to_screen = _bind(u, "ClientToScreen", boolean, hwnd, ctypes.POINTER(point))
        self._window_at = _bind(u, "WindowFromPoint", hwnd, point)
        self._cursor = _bind(u, "GetCursorPos", boolean, ctypes.POINTER(point))
        self._set_cursor = _bind(u, "SetCursorPos", boolean, ctypes.c_int, ctypes.c_int)
        self._key_state = _bind(u, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
        self._post = _bind(u, "PostMessageW", boolean, hwnd, uint, wintypes.WPARAM, wintypes.LPARAM)
        self._set_dpi = _bind(u, "SetThreadDpiAwarenessContext", handle, handle)
        self._open_process = _bind(k, "OpenProcess", handle, dword, boolean, dword)
        self._close_handle = _bind(k, "CloseHandle", boolean, handle)
        self._create_mutex = _bind(k, "CreateMutexW", handle, wintypes.LPVOID, boolean, wintypes.LPCWSTR)
        self._release_mutex = _bind(k, "ReleaseMutex", boolean, handle)
        self._process_name = _bind(k, "QueryFullProcessImageNameW", boolean, handle, dword, wintypes.LPWSTR,
                                   ctypes.POINTER(dword))
        time_p = ctypes.POINTER(wintypes.FILETIME)
        self._process_times = _bind(k, "GetProcessTimes", boolean, handle, time_p, time_p, time_p, time_p)

    @contextmanager
    def exclusive(self):
        # Navigation and saving must not operate the same game window concurrently.
        ctypes.set_last_error(0)
        handle = self._create_mutex(None, True, f"Local\\AtlasEU4_Save_{self.pid}_{self.process_start_ms}")
        if not handle:
            raise GameInputError("save_busy", "Windows nie umożliwił teraz obsługi okna gry.")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS, the caller owns no mutex
            self._close_handle(handle)
            raise GameInputError("save_busy", "Trwa obsługa innego polecenia w oknie EU4. Spróbuj ponownie.")
        try:
            yield
        finally:
            self._release_mutex(handle)
            self._close_handle(handle)

    @contextmanager
    def _physical_dpi(self):
        old = self._set_dpi(-4)  # Per-monitor-aware v2, scoped to this synchronous operation.
        if not old:
            raise GameInputError("window_unavailable", "Windows nie potwierdził skali okna gry.")
        try:
            yield
        finally:
            self._set_dpi(old)

    def _belongs_to_game(self, hwnd):
        pid = wintypes.DWORD()
        return (hwnd and self._thread_pid(hwnd, ctypes.byref(pid)) == self.thread and pid.value == self.pid
                and self._visible(hwnd) and not self._iconic(hwnd) and self._ancestor(hwnd, 3) == hwnd)

    def _choose_window(self):
        matches = []

        @self._callback
        def collect(hwnd, _):
            rect = wintypes.RECT()
            if (self._belongs_to_game(hwnd) and self._client_rect(hwnd, ctypes.byref(rect))
                    and (rect.right, rect.bottom) == self.size):
                matches.append(hwnd)
            return True

        with self._physical_dpi():
            self._enum_windows(collect, 0)
        if len(matches) != 1:
            raise GameInputError("window_unavailable", "Windows nie potwierdził właściwego okna EU4.")
        return matches[0]

    def __enter__(self):
        self.process = self._open_process(0x1000, False, self.pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not self.process:
            raise GameInputError("window_unavailable", "Windows nie potwierdził procesu EU4.")
        try:
            name = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(name))
            if (not self._process_name(self.process, 0, name, ctypes.byref(size))
                    or Path(name.value) != self.exe):
                raise GameInputError("window_unavailable", "Okno nie należy do wskazanej instalacji EU4.")
            times = [wintypes.FILETIME() for _ in range(4)]
            if not self._process_times(self.process, *(ctypes.byref(value) for value in times)):
                raise GameInputError("window_unavailable", "Nie udało się sprawdzić procesu EU4.")
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            if created // 10_000 - 11_644_473_600_000 != self.process_start_ms:
                raise GameInputError("session_changed", "Proces EU4 zmienił się. Spróbuj ponownie.")
            self.hwnd = self._choose_window()
        except BaseException:
            self._close_handle(self.process)
            raise
        return self

    def __exit__(self, *_):
        try:
            if self.restore_safe and self.origin is not None:
                with self._physical_dpi():
                    self._guard_window()
                    if self._read_cursor() == self.expected_cursor and self._at_game(self.origin):
                        self._set_cursor(*self.origin)
        except GameInputError:
            pass
        finally:
            self._close_handle(self.process)

    async def focus(self):
        self._guard_input()
        if self._foreground() != self.hwnd:
            if not self._belongs_to_game(self.hwnd):
                raise GameInputError("window_unavailable", "Okno gry zmieniło się. Spróbuj ponownie.")
            self._set_foreground(self.hwnd)
        end = monotonic() + 2.5
        while self._foreground() != self.hwnd and monotonic() < end:
            self._guard_input()
            await asyncio.sleep(0.08)
        self._guard_window()

    def _read_cursor(self):
        point = wintypes.POINT()
        if not self._cursor(ctypes.byref(point)):
            raise GameInputError("pointer_unavailable", "Windows nie udostępnił położenia wskaźnika.")
        return point.x, point.y

    def _at_game(self, screen_point):
        return self._window_at(wintypes.POINT(*screen_point)) == self.hwnd

    def _screen(self, xy):
        x, y = xy
        rect = wintypes.RECT()
        point = wintypes.POINT(x, y)
        if (not self._client_rect(self.hwnd, ctypes.byref(rect)) or (rect.right, rect.bottom) != self.size
                or not 0 <= x < min(32768, rect.right)
                or not 0 <= y < min(32768, rect.bottom) or not self._to_screen(self.hwnd, ctypes.byref(point))):
            raise GameInputError("window_unavailable", "Położenie przycisku nie mieści się w oknie EU4.")
        return point.x, point.y

    def _guard_window(self):
        self._guard_input()
        if self._foreground() != self.hwnd or not self._belongs_to_game(self.hwnd):
            self.restore_safe = False
            raise GameInputError("game_not_focused", "Przełącz się do okna EU4 i ponów polecenie.")

    def _guard_input(self):
        self.check_input()
        if self._has_manual_input():
            self.restore_safe = False
            raise GameInputError("player_input", "Puść klawisze lub przyciski myszy i spróbuj ponownie.")

    def _has_manual_input(self):
        return any(self._key_state(key) < 0 for key in (0x01, 0x02, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x5B, 0x5C))

    def _guard_cursor(self):
        self._guard_window()
        current = self._read_cursor()
        if self.expected_cursor is not None and current != self.expected_cursor:
            self.restore_safe = False
        return current

    def pointer_at(self, xy):
        with self._physical_dpi():
            return self._guard_cursor() == self._screen(xy)

    def require_pointer(self, xy):
        with self._physical_dpi():
            self._require_pointer(xy)

    def _require_pointer(self, xy):
        current = self._guard_cursor()
        if current != self._screen(xy):
            raise _pointer_moved()
        if not self._at_game(current):
            raise GameInputError("game_covered", "Okno EU4 zostało zasłonięte. Odsłoń je i spróbuj ponownie.")

    def move(self, xy):
        with self._physical_dpi():
            current = self._guard_cursor()
            target = self._screen(xy)
            if not self._at_game(target):
                raise GameInputError("game_covered", "Okno EU4 jest częściowo zasłonięte. Odsłoń je i spróbuj ponownie.")
            if self.origin is None:
                self.origin = current
            if not self._set_cursor(*target):
                raise GameInputError("pointer_unavailable", "Windows nie pozwolił ustawić wskaźnika w oknie gry.")
            self.expected_cursor = target

    def leave_cursor(self, xy):
        self.require_pointer(xy)
        self.restore_safe = False

    def _send(self, message, key, detail):
        if not self._post(self.hwnd, message, key, detail):
            raise GameInputError("input_unavailable", "Windows nie przekazał akcji do gry.")

    def click(self, xy):
        with self._physical_dpi():
            self._require_pointer(xy)
            x, y = xy
            detail = x | (y << 16)
            self._send(0x0201, 1, detail)  # WM_LBUTTONDOWN
            try:
                self._send(0x0202, 0, detail)  # WM_LBUTTONUP
            except GameInputError as exc:
                exc.click_may_have_landed = True
                self.restore_safe = False
                raise
