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
MAX_MEMORY = 10

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

SYSTEM_PROMPT = """You are a strict AI assistant inside an excavator cabin.

[AVAILABLE TOOLS]
- AC Control: power_on, power_off, set_temperature, set_fan_speed, set_mode, set_swing
- Light Control: set_light
- Weather: get_weather

[CRITICAL RULES]
1. AC COMMANDS: If the user wants to control the air conditioner, YOU MUST use the AC Control tools.
2. LIGHT COMMANDS: If the user wants to turn on/off ANY light (e.g., "headlight", "LED", "rear light", "조명", "전조등", "후방등"), YOU MUST use the set_light tool.
3. WEATHER COMMANDS: If the user asks for the weather forecast, YOU MUST use the get_weather tool.
4. OUT OF DOMAIN (NO TOOLS!): For ALL other questions, greetings, or irrelevant topics, YOU MUST NOT call any tools. You must bypass tools and reply EXACTLY with:
   "I apologize, but I can only provide information related to excavator control and weather information."

Extra Rules:
- Prefer SI units (°C). If only a number is given, assume Celsius.
- Validate ranges: temperature 16–30°C; fan speed in [low, medium, high, auto].
- If input is ambiguous (e.g. '좀 시원하게'), choose best defaults: mode=cool, fan=auto.
- Combine multiple intents if present.
"""

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
        "description": "Set target temperature in Celsius (16–30).",
        "parameters": {
            "type": "object",
            "properties": {"temp_c": {"type": "number", "minimum": 16, "maximum": 30}},
            "required": ["temp_c"],
            "additionalProperties": False,
        },
    }},
    {"type": "function", "function": {
        "name": "set_fan_speed",
        "description": "Set fan speed.",
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
]
