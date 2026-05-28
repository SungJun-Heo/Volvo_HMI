from pathlib import Path

# ── 날씨 ──────────────────────────────────────────────────────────────────────
TIME_MAP = {"morning": "0800", "afternoon": "1400", "evening": "1700", "night": "2000"}
DEFAULT_LOCATION = {"nx": 98, "ny": 76}

# ── 로그 ──────────────────────────────────────────────────────────────────────
LOG_DIR    = Path("logs")
JSONL_PATH = LOG_DIR / "llm_log.jsonl"
CSV_PATH   = LOG_DIR / "llm_log.csv"
CSV_HEADERS = ["timestamp", "session_id", "user_text", "reply", "tool_calls", "ok"]

# ── LLM ───────────────────────────────────────────────────────────────────────
MAX_MEMORY = 3

# ac = [power, temp, speed, mode, swing]
AC_IDX_POWER = 0
AC_IDX_TEMP  = 1
AC_IDX_SPEED = 2
AC_IDX_MODE  = 3
AC_IDX_SWING = 4

AC_POWER = {"on": 1, "off": 0}

AC_SPEED = {
    "auto":   0,
    "low":    1,
    "medium": 3,
    "high":   5,
}

AC_MODE = {
    "auto": 0,
    "cool": 1,
    "heat": 2,
    "fan":  3,
    "dry":  4,
}

AC_SWING = {"on": 1, "off": 0}


TOOLS = [
    {"type": "function", "function": {
        "name": "power_on",
        "description": "Turn AC power on.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "power_off",
        "description": "Turn AC power off.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    }},
    {"type": "function", "function": {
        "name": "set_temperature",
        "description": "Set target temperature in Celsius (16–30). (필수 규칙: '덥다' → 18도, '춥다' → 26도, '조금/약간' → 1~2도 조절)",
        "parameters": {
            "type": "object",
            "properties": {"temp_c": {"type": "number", "minimum": 16, "maximum": 30}},
            "required": ["temp_c"],
            "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "set_fan_speed",
        "description": "Set fan speed. (키워드: 약하게/조용히=low, 중간=medium, 강하게/세게=high, 자동=auto)",
        "parameters": {
            "type": "object",
            "properties": {"level": {"type": "string", "enum": ["low", "medium", "high", "auto"]}},
            "required": ["level"],
            "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "set_mode",
        "description": "Set AC mode.",
        "parameters": {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["cool", "heat", "fan", "auto", "dry"]}},
            "required": ["mode"],
            "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "set_swing",
        "description": "Set swing on/off.",
        "parameters": {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
            "required": ["state"],
            "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Get weather information.",
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "description": "'today' or 'tomorrow'"},
                "time":   {"type": "string", "enum": ["morning", "afternoon", "evening", "night"]},
                "intent": {"type": "string", "enum": ["summary", "yesno"]},
            },
            "required": ["date"],
        },
    }},
    {"type": "function", "function": {
        "name": "set_light",
        "description": "Turn the excavator's light (headlight, LED, rear light) on or off.",
        "parameters": {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
            "required": ["state"],
            "additionalProperties": False,
        },
    }},
    # 신기능
    {"type": "function", "function": {
        "name": "get_arm_status",
        "description": "굴착기의 암 관절 각도(joints)와 버켓의 지면 기준 높이/깊이(depth)를 확인합니다. 사용자가 암 각도, 버켓 위치를 묻거나 신기능(버켓 위치 안내 등)에 대해 물어볼 때 이 도구를 호출하세요.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
    }},
]
