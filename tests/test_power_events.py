import unittest
from unittest.mock import MagicMock

from power_events import (PowerSession, WindowsPowerMonitor, WM_POWERBROADCAST,
                          WM_QUERYENDSESSION, WM_ENDSESSION, PBT_APMSUSPEND,
                          PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND)


class ResumeTests(unittest.TestCase):
    def test_manual_connection_resumes_with_bounded_usb_retry(self):
        state = PowerSession()
        state.suspend(True)
        self.assertFalse(state.should_reconnect(0, running=False, connected=False))
        state.resume(100)
        self.assertTrue(state.should_reconnect(100, running=False, connected=False))
        self.assertFalse(state.should_reconnect(101, running=False, connected=False))
        self.assertTrue(state.should_reconnect(102, running=False, connected=False))
        self.assertFalse(state.should_reconnect(103, running=True, connected=False))
        self.assertFalse(state.should_reconnect(131, running=False, connected=False))

    def test_disconnected_session_stays_disconnected_after_wake(self):
        state = PowerSession()
        state.suspend(False)
        state.resume(0)
        self.assertFalse(state.should_reconnect(0, running=False, connected=False))

    def test_duplicate_notifications_preserve_intent_and_do_not_reset_retries(self):
        state = PowerSession()
        state.suspend(True)
        state.suspend(False)
        state.resume(10)
        state.resume(20)
        self.assertTrue(state.should_reconnect(20, running=False, connected=False))
        self.assertFalse(state.should_reconnect(41, running=False, connected=False))

    def test_cancel_prevents_old_connection_intent_from_reopening_device(self):
        state = PowerSession()
        state.suspend(True)
        state.cancel_reconnect()
        state.resume(10)
        self.assertFalse(state.should_reconnect(10, running=False, connected=False))
        state.suspend(True)
        state.resume(20)
        state.cancel_reconnect()
        self.assertFalse(state.should_reconnect(20, running=False, connected=False))

    def test_connected_result_clears_retry_and_second_sleep_preserves_pending_intent(self):
        state = PowerSession()
        state.suspend(True)
        state.resume(10)
        state.suspend(False)  # USB was not ready before the next suspension.
        state.resume(15)
        self.assertTrue(state.should_reconnect(15, running=False, connected=False))
        self.assertFalse(state.should_reconnect(16, running=True, connected=True))
        self.assertFalse(state.should_reconnect(17, running=False, connected=False))


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.monitor = WindowsPowerMonitor.__new__(WindowsPowerMonitor)
        self.monitor.closed = False
        self.monitor._shutdown_queried = False
        self.monitor._previous = 123
        self.monitor.user = MagicMock()
        self.monitor.user.CallWindowProcW.return_value = 77
        self.monitor.callback = MagicMock()

    def test_power_notifications_forward_and_preserve_original_window_result(self):
        for value, expected in ((PBT_APMSUSPEND, "suspend"),
                                (PBT_APMRESUMEAUTOMATIC, "resume"),
                                (PBT_APMRESUMESUSPEND, "resume")):
            self.assertEqual(self.monitor._window_proc(10, WM_POWERBROADCAST, value, 0), 77)
            self.monitor.callback.assert_called_with(expected)

    def test_shutdown_accepts_immediately_and_cancellation_resumes(self):
        self.assertEqual(self.monitor._window_proc(10, WM_QUERYENDSESSION, 0, 0), 1)
        self.monitor.callback.assert_called_with("shutdown")
        self.assertEqual(self.monitor._window_proc(10, WM_ENDSESSION, 0, 0), 0)
        self.monitor.callback.assert_called_with("resume")
        self.monitor.callback.reset_mock()
        self.monitor._window_proc(10, WM_ENDSESSION, 0, 0)
        self.monitor.callback.assert_not_called()

    def test_unknown_messages_always_reach_tk_and_closed_monitor_is_inert(self):
        self.assertEqual(self.monitor._window_proc(10, 0x1234, 2, 3), 77)
        self.monitor.user.CallWindowProcW.assert_called_with(123, 10, 0x1234, 2, 3)
        self.monitor.closed = True
        self.monitor._window_proc(10, WM_POWERBROADCAST, PBT_APMSUSPEND, 0)
        self.monitor.callback.assert_not_called()
