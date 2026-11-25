import unittest
from collections import deque
from contextlib import nullcontext
from unittest.mock import Mock, patch

from campaign_ui_driver import GameInputError, InputControl, _GameWindow


class InputControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.control = InputControl()
        self.messages = deque()
        self.win = Mock()
        self.win.RegisterHotKey.return_value = True
        self.win.PeekMessageW.side_effect = self._peek
        self.enterContext(patch("campaign_ui_driver.sys.platform", "win32"))
        self.enterContext(patch("campaign_ui_driver.ctypes.WinDLL", return_value=self.win, create=True))
        self.addCleanup(self.control.close)

    def _peek(self, message, hwnd, first, last, remove):
        self.assertEqual((hwnd, first, last, remove), (-1, 0x0312, 0x0312, 1))
        if not self.messages:
            return False
        message._obj.wParam = self.messages.popleft()
        return True

    def test_only_a_ui_action_claims_f9(self):
        self.assertFalse(self.control.resume()["resumed"])
        self.win.RegisterHotKey.assert_not_called()
        self.control.begin()
        self.control.begin()
        self.win.RegisterHotKey.assert_called_once_with(None, self.control._HOTKEY_ID, 0x4000, 0x78)
        self.control.close()
        self.win.UnregisterHotKey.assert_called_once_with(None, self.control._HOTKEY_ID)

    async def test_short_press_between_actions_stays_paused_and_cancels_old_action(self):
        before = self.control.begin()
        before()
        self.messages.append(self.control._HOTKEY_ID)

        for _ in range(2):
            with self.assertRaises(GameInputError) as stopped:
                self.control.begin()
            self.assertEqual(stopped.exception.code, "ui_control_paused")

        self.assertEqual(self.control.resume(), {"resumed": True, "paused": False, "handover_key": "F9"})
        with self.assertRaises(GameInputError) as stopped:
            before()
        self.assertEqual(stopped.exception.code, "ui_control_interrupted")
        self.control.begin()()

    async def test_pause_prevents_reclaiming_focus(self):
        check_input = self.control.begin()
        self.messages.append(self.control._HOTKEY_ID)
        window = _GameWindow.__new__(_GameWindow)
        window.check_input = check_input
        window._set_foreground = Mock()

        with self.assertRaises(GameInputError) as stopped:
            await window.focus()

        self.assertEqual(stopped.exception.code, "ui_control_paused")
        window._set_foreground.assert_not_called()

    def test_busy_hotkey_can_be_retried_after_release(self):
        self.win.RegisterHotKey.side_effect = [False, True]
        with patch("campaign_ui_driver.ctypes.get_last_error", return_value=1409, create=True):
            with self.assertRaises(GameInputError) as conflict:
                self.control.begin()
        self.assertEqual(conflict.exception.code, "ui_hotkey_conflict")
        self.control.begin()()

    def test_click_does_not_use_moved_cursor_and_move_does_not_pause(self):
        window = _GameWindow.__new__(_GameWindow)
        window.hwnd = 101
        window.origin = (20, 20)
        window.expected_cursor = (50, 20)
        window.restore_safe = True
        window.check_input = self.control.begin()
        window._physical_dpi = nullcontext
        window._foreground = Mock(return_value=window.hwnd)
        window._belongs_to_game = Mock(return_value=True)
        window._has_manual_input = Mock(return_value=False)
        window._read_cursor = Mock(return_value=(150, 120))
        window._at_game = Mock(return_value=True)
        window._screen = lambda xy: xy
        window._set_cursor = Mock(return_value=True)
        window._post = Mock(return_value=True)

        with self.assertRaises(GameInputError) as rejected:
            window.click((50, 20))
        self.assertEqual(rejected.exception.code, "pointer_moved")
        window._post.assert_not_called()

        window.move((50, 20))
        window._set_cursor.assert_called_once_with(50, 20)
        self.assertFalse(window.restore_safe)

        window._has_manual_input.return_value = True
        with self.assertRaises(GameInputError) as rejected:
            window.move((50, 20))
        self.assertEqual(rejected.exception.code, "player_input")
        window._set_cursor.assert_called_once_with(50, 20)
        window._has_manual_input.return_value = False
        self.control.begin()()
