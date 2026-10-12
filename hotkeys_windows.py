from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes
from typing import Callable

VK_CAPITAL = 0x14
VK_Q = 0x51
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WH_KEYBOARD_LL = 13
LLKHF_INJECTED = 0x10
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class CapsQState:
    """Pure hotkey state machine; testable without Windows or Qt.

    Returns (suppress_event, trigger_hud, replay_caps_tap).
    """
    def __init__(self):
        self.caps_held = False
        self.caps_used = False
        self.q_suppressed = False
        self.chord_used = False

    def handle(self, vk: int, down: bool) -> tuple[bool, bool, bool]:
        if vk == VK_CAPITAL:
            if down:
                if not self.caps_held:
                    self.caps_held = True
                    self.caps_used = False
                    self.chord_used = False
                return True, False, False
            if self.caps_held:
                tap = not self.caps_used and not self.chord_used
                self.caps_held = False
                self.caps_used = False
                self.chord_used = False
                return True, False, tap
            return False, False, False
        if vk == VK_Q and self.q_suppressed:
            if not down:
                self.q_suppressed = False
            return True, False, False
        if vk == VK_Q and down and self.caps_held and not self.caps_used:
            self.q_suppressed = True
            self.chord_used = True
            return True, True, False
        if down and self.caps_held and not self.caps_used and not self.chord_used:
            # Caps+other key: keep ordinary CapsLock behavior; no hotkey.
            self.caps_used = True
            return False, False, True
        return False, False, False


if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    ULONG_PTR = ctypes.c_size_t

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                    ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("_align", ctypes.c_void_p * 4)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]

    LOW_LEVEL_PROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LOW_LEVEL_PROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = LRESULT
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostThreadMessageW.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _send_caps_tap() -> None:
    if sys.platform != "win32":
        return
    events = (INPUT * 2)(
        INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(VK_CAPITAL, 0, 0, 0, 0))),
        INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(VK_CAPITAL, 0, KEYEVENTF_KEYUP, 0, 0))),
    )
    user32.SendInput(2, events, ctypes.sizeof(INPUT))


class CapsQHook:
    def __init__(self, on_hotkey: Callable[[int], None]):
        self.on_hotkey = on_hotkey
        self.state = CapsQState()
        self.thread: threading.Thread | None = None
        self.thread_id = 0
        self._hook = None
        self._callback = None
        self._ready = threading.Event()
        self.error: str | None = None

    def start(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows에서만 사용할 수 있습니다.")
        self.thread = threading.Thread(target=self._loop, daemon=True, name="KanaShift-Hotkey")
        self.thread.start()
        if not self._ready.wait(4):
            raise RuntimeError("키보드 후크 초기화 시간이 초과되었습니다.")
        if self.error:
            raise RuntimeError(self.error)

    def _loop(self) -> None:
        self.thread_id = kernel32.GetCurrentThreadId()

        @LOW_LEVEL_PROC
        def callback(code, wparam, lparam):
            if code < 0 or wparam not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                return user32.CallNextHookEx(self._hook, code, wparam, lparam)
            event = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if event.flags & LLKHF_INJECTED:
                return user32.CallNextHookEx(self._hook, code, wparam, lparam)
            down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            swallow, fire, tap = self.state.handle(event.vkCode, down)
            if tap:
                _send_caps_tap()
            if fire:
                try:
                    # Read focus before overlay takes focus, on physical keydown.
                    self.on_hotkey(0)
                except Exception:
                    pass
            if swallow:
                return 1
            return user32.CallNextHookEx(self._hook, code, wparam, lparam)

        self._callback = callback
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, module, 0)
        if not self._hook:
            self.error = f"키보드 후크 등록 실패 (Win32 {ctypes.get_last_error()})"
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def stop(self) -> None:
        if self.thread_id and self.thread and self.thread.is_alive():
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            self.thread.join(timeout=1)
