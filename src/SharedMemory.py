import threading
from .constants import AC_IDX_POWER, AC_IDX_TEMP, AC_IDX_SPEED, AC_IDX_MODE, AC_IDX_SWING, AC_POWER, AC_SPEED, AC_MODE, AC_SWING


class SharedMemory:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = True
        self.command_event = threading.Event()
        self.llm_input = ""
        self.llm_output = None   # list[dict] (tool_calls) or str (text)
        self.status = {
            "headlight": 0,
            "ac": [0, 24, 0, 0, 0],  # power, temp, speed, mode, swing
            "joints": [0.0, 0.0, 0.0],
            "depth": None
        }
        # GUI state
        self.llm_processing = False
        self.stt_active = False
        self.stt_trigger = threading.Event()

    # ── 범용 접근 ──────────────────────────────────────────────────────────────

    def set_value(self, key, value):
        with self.lock:
            self.status[key] = value

    def get_value(self, key, default=None):
        with self.lock:
            return self.status.get(key, default)

    def get_all(self):
        with self.lock:
            return self.status.copy()

    # ── AC 제어 ────────────────────────────────────────────────────────────────

    def set_ac_power(self, state: str):
        with self.lock:
            self.status["ac"][AC_IDX_POWER] = AC_POWER[state]

    def set_ac_temperature(self, temp_c: int):
        if not (16 <= temp_c <= 30):
            raise ValueError(f"온도 범위 초과: {temp_c}")
        with self.lock:
            self.status["ac"][AC_IDX_TEMP] = temp_c

    def set_ac_fan_speed(self, level: str):
        with self.lock:
            self.status["ac"][AC_IDX_SPEED] = AC_SPEED[level]

    def set_ac_mode(self, mode: str):
        with self.lock:
            self.status["ac"][AC_IDX_MODE] = AC_MODE[mode]

    def set_ac_swing(self, state: str):
        with self.lock:
            self.status["ac"][AC_IDX_SWING] = AC_SWING[state]

    # ── 조명 제어 ──────────────────────────────────────────────────────────────

    def set_headlight(self, state: str):
        with self.lock:
            self.status["headlight"] = 1 if state == "on" else 0

    # ── 읽기 ───────────────────────────────────────────────────────────────────

    def get_ac_state(self) -> dict:
        with self.lock:
            ac = self.status["ac"]
            return {
                "power": ac[AC_IDX_POWER],
                "temp":  ac[AC_IDX_TEMP],
                "speed": ac[AC_IDX_SPEED],
                "mode":  ac[AC_IDX_MODE],
                "swing": ac[AC_IDX_SWING],
            }

    def get_headlight(self) -> int:
        with self.lock:
            return self.status["headlight"]
