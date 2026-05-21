"""Test key normalization with exact key codes observed in VNC debug session."""
from pynput import keyboard as pynput_keyboard
from app.config.settings import CONFIG
from app.orchestration.orchestrator import Orchestrator
import queue


class _FakeTray:
    def set_state(self, s): pass

class _FakeAudio:
    def start_recording(self): pass
    def stop_recording(self): import numpy as np; return np.zeros(0, dtype="float32")

class _FakeStt:
    is_enabled = True
    def transcribe(self, a): return ("", "pt")
    def disable(self): pass


eq = queue.Queue()
orch = Orchestrator(CONFIG, _FakeTray(), _FakeAudio(), _FakeStt(), lambda t: None, eq)
orch._listener.stop()

KEY_R = pynput_keyboard.KeyCode.from_char("r")

# Case 1: Ctrl+Shift+R — 'r' arrives as '\x12' (Ctrl control char, ASCII 18)
r_ctrl_shift = pynput_keyboard.KeyCode(char="\x12")
n1 = orch._normalize_key(r_ctrl_shift)
ok1 = n1 == KEY_R
print(f"[{'PASS' if ok1 else 'FAIL'}] Ctrl+Shift+R: '\\x12' -> {n1!r}  (esperado: {KEY_R!r})")

# Case 2: Ctrl+Alt+R — 'r' arrives as KeyCode(vk=82) without .char
r_alt = pynput_keyboard.KeyCode(vk=82)
n2 = orch._normalize_key(r_alt)
ok2 = n2 == KEY_R
print(f"[{'PASS' if ok2 else 'FAIL'}] Ctrl+Alt+R:   vk=82    -> {n2!r}  (esperado: {KEY_R!r})")

# Case 3: Key.shift (generic) in shift alternatives
shift_generic = pynput_keyboard.Key.shift
shift_in_parts = orch._is_hotkey_key(shift_generic)
print(f"[{'PASS' if shift_in_parts else 'FAIL'}] Key.shift genérico reconhecido como parte do hotkey")

# Case 4: Full combo simulation — ctrl_l + shift(generic) + r as \x12
print()
print("Simulando teclas exatas do debug_keys.py (Ctrl+Shift+R no VNC):")
orch._current_keys.clear()
orch._current_keys.add(orch._normalize_key(pynput_keyboard.Key.ctrl_l))
orch._current_keys.add(orch._normalize_key(pynput_keyboard.Key.shift))
orch._current_keys.add(orch._normalize_key(pynput_keyboard.KeyCode(char="\x12")))
complete = orch._is_hotkey_complete()
print(f"  current_keys normalizado: {orch._current_keys}")
print(f"  is_hotkey_complete: {complete}")
print(f"  [{'PASS' if complete else 'FAIL'}] PTT_START {'SERIA' if complete else 'NAO SERIA'} enfileirado")
