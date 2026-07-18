from __future__ import annotations

import ctypes
import time


CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_V = 0x56


class WindowsAdminChatSender:
    """Paste a prepared iRacing admin command into the sim chat window.

    iRacing's SDK can open the chat box, but dynamic hosted-admin commands still
    need text entry. This sender uses the Windows clipboard plus Ctrl+V/Enter so
    no extra dependency is required.
    """

    def __init__(self, user32=None, kernel32=None, delay_seconds=0.08):
        self.user32 = user32 or ctypes.windll.user32
        self.kernel32 = kernel32 or ctypes.windll.kernel32
        self.delay_seconds = float(delay_seconds)

    def send(self, text):
        text = str(text or "").strip()
        if not text:
            return False
        if not self.set_clipboard_text(text):
            return False
        time.sleep(self.delay_seconds)
        self.press_ctrl_v()
        time.sleep(self.delay_seconds)
        self.press_key(VK_RETURN)
        return True

    def set_clipboard_text(self, text):
        data = (text + "\0").encode("utf-16-le")
        if not self.user32.OpenClipboard(None):
            return False
        handle = None
        try:
            self.user32.EmptyClipboard()
            handle = self.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                return False
            locked = self.kernel32.GlobalLock(handle)
            if not locked:
                return False
            try:
                ctypes.memmove(locked, data, len(data))
            finally:
                self.kernel32.GlobalUnlock(handle)
            if not self.user32.SetClipboardData(CF_UNICODETEXT, handle):
                return False
            handle = None
            return True
        finally:
            self.user32.CloseClipboard()

    def press_ctrl_v(self):
        self.key_down(VK_CONTROL)
        self.press_key(VK_V)
        self.key_up(VK_CONTROL)

    def press_key(self, virtual_key):
        self.key_down(virtual_key)
        self.key_up(virtual_key)

    def key_down(self, virtual_key):
        self.user32.keybd_event(int(virtual_key), 0, 0, 0)

    def key_up(self, virtual_key):
        self.user32.keybd_event(int(virtual_key), 0, KEYEVENTF_KEYUP, 0)
