"""Windows tray bridge; callbacks enqueue actions instead of touching Tk."""
import threading

import pystray
from branding import icon_image


class MixerTray:
    def __init__(self, actions):
        self.actions = actions
        self.ready = threading.Event()
        self.icon = pystray.Icon("MixerHub", icon_image(), "Mixer Hub", menu=pystray.Menu(
            pystray.MenuItem("Open Mixer Hub", lambda: actions.put("show"), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Mixer Hub", lambda: actions.put("quit")),
        ))
        self.thread = None

    def start(self):
        def setup(icon):
            icon.visible = True
            self.ready.set()
        # pystray explicitly supports a separate event-loop thread on Windows.
        self.thread = threading.Thread(target=lambda: self.icon.run(setup), name="Mixer tray", daemon=True)
        self.thread.start()

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.ready.wait(timeout=2)
        self.icon.stop()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
