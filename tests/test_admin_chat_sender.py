from production.admin_chat_sender import WindowsAdminChatSender


class FakeUser32:
    def __init__(self):
        self.windows = {
            101: "RGC Producer Assist - Browser",
            202: "iRacing.com Simulator",
        }
        self.visible = {101: True, 202: True}
        self.foreground = 101
        self.set_foreground_calls = []
        self.keys = []

    def EnumWindows(self, callback, lparam):
        for hwnd in list(self.windows):
            keep_going = callback(hwnd, lparam)
            if not keep_going:
                break
        return True

    def IsWindowVisible(self, hwnd):
        return self.visible.get(int(hwnd), False)

    def GetWindowTextLengthW(self, hwnd):
        return len(self.windows.get(int(hwnd), ""))

    def GetWindowTextW(self, hwnd, buffer, max_count):
        title = self.windows.get(int(hwnd), "")[: max_count - 1]
        buffer.value = title
        return len(title)

    def IsIconic(self, hwnd):
        return False

    def ShowWindow(self, hwnd, mode):
        return True

    def GetForegroundWindow(self):
        return self.foreground

    def SetForegroundWindow(self, hwnd):
        self.foreground = int(hwnd)
        self.set_foreground_calls.append(int(hwnd))
        return True

    def keybd_event(self, virtual_key, _scan, flags, _extra):
        self.keys.append((int(virtual_key), int(flags)))


class SenderSpy(WindowsAdminChatSender):
    def __init__(self, user32):
        super().__init__(user32=user32, kernel32=object(), delay_seconds=0)
        self.clipboard_text = ""

    def set_clipboard_text(self, text):
        self.clipboard_text = text
        return True


def test_admin_chat_sender_focuses_iracing_window_before_paste():
    user32 = FakeUser32()
    sender = SenderSpy(user32)

    assert sender.send("!yellow") is True

    assert user32.foreground == 202
    assert user32.set_foreground_calls == [202]
    assert sender.clipboard_text == "!yellow"
    assert user32.keys


def test_admin_chat_sender_can_copy_without_focusing_iracing_window():
    user32 = FakeUser32()
    sender = SenderSpy(user32)

    assert sender.copy_only("!yellow") is True

    assert user32.foreground == 101
    assert user32.set_foreground_calls == []
    assert sender.clipboard_text == "!yellow"
    assert user32.keys == []


def test_admin_chat_sender_uses_powershell_clipboard_fallback():
    class FallbackSender(SenderSpy):
        def __init__(self, user32):
            super().__init__(user32)
            self.fallback_text = ""

        def set_clipboard_text(self, text):
            return False

        def set_clipboard_text_with_powershell(self, text):
            self.fallback_text = text
            return True

    user32 = FakeUser32()
    sender = FallbackSender(user32)

    assert sender.copy_only("!yellow") is True
    assert sender.fallback_text == "!yellow"
    assert user32.foreground == 101


def test_admin_chat_sender_refuses_to_paste_when_iracing_window_is_missing():
    user32 = FakeUser32()
    user32.windows = {101: "RGC Producer Assist - Browser"}
    sender = SenderSpy(user32)

    assert sender.send("!yellow") is False

    assert sender.clipboard_text == ""
    assert user32.foreground == 101
