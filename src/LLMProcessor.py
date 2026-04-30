import os
import threading
import json
import csv
import uuid
import requests
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
from .constants import AC_POWER_ON, AC_POWER_OFF, AC_SPEED, AC_MODE, AC_SWING_ON, AC_SWING_OFF


class LLMProcessor(threading.Thread):

    _TIME_MAP = {"morning": "0800", "afternoon": "1400", "evening": "1700", "night": "2000"}

    _KMA_SERVICE_KEY = "XDFWE2EF8u0+ZA6IOpdyKF7ugHMzrtDwlCGDzn0LQIiU0zHui/oRyAcyxR2hDthrlRlFW6Zo7IiElJw9Ugeguw=="
    _DEFAULT_LOCATION = {"nx": 98, "ny": 76}

    _LOG_DIR   = Path("logs")
    _JSONL_PATH = _LOG_DIR / "llm_log.jsonl"
    _CSV_PATH   = _LOG_DIR / "llm_log.csv"
    _CSV_HEADERS = ["timestamp", "session_id", "user_text", "reply", "tool_calls", "ok"]

    _MAX_MEMORY = 10

    _SYSTEM_PROMPT = """You are a strict AI assistant inside an excavator cabin.

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

    _TOOLS = [
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

    # ── 생명주기 ──────────────────────────────────────────────────────────────

    def __init__(self, shm, base_url=None, model="llama3.1:8b"):
        base_url = base_url or os.getenv("LLM_BASE_URL", "http://bore.pub:59831/v1")
        super().__init__(daemon=True)
        self.shm = shm
        self.model = model
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.chat_memory = []
        self.session_id = str(uuid.uuid4())
        self._LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _ping(self) -> bool:
        try:
            print("[LLM] 서버 연결 확인 중...")
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0,
            )
            print("[LLM] 서버 연결 성공")
            return True
        except Exception as e:
            print(f"[LLM] 서버 연결 실패: {e}")
            return False

    def run(self):
        if not self._ping():
            self.shm.is_running = False
            return
        while self.shm.is_running:
            self.shm.command_event.wait()
            text = self.shm.last_command
            self.shm.command_event.clear()
            if text:
                reply = self._process_command(text)
                print(f"[LLM] {reply}")
                # TODO: TTS 모듈로 전달

    def stop(self):
        self.shm.is_running = False
        self.shm.command_event.set()  # wait() 블로킹 해제

    # ── 핵심 처리 ─────────────────────────────────────────────────────────────

    def _process_command(self, text: str) -> str:
        self.chat_memory.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": self._SYSTEM_PROMPT}] + self.chat_memory

        record = {
            "timestamp":  datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "user_text":  text,
            "reply":      "",
            "tool_calls": [],
            "ok":         True,
        }

        try:
            print(f"[LLM →] \"{text}\"")
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message
            tool_names = [tc.function.name for tc in (msg.tool_calls or [])]
            print(f"[LLM ←] tool_calls={tool_names if tool_names else 'none'}")

            if not getattr(msg, "tool_calls", None):
                reply = (msg.content or "요청을 이해했어요.").strip()
            else:
                confirmations = []
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments or "{}")
                    record["tool_calls"].append({"name": name, "args": args})

                    # 온도 범위 이중 검증
                    if name == "set_temperature":
                        t = float(args.get("temp_c", 0))
                        if not (16 <= t <= 30):
                            reply = "온도는 16~30°C 사이로만 설정할 수 있어요."
                            record["reply"] = reply
                            record["ok"] = False
                            self._save_log(record)
                            self.chat_memory.append({"role": "assistant", "content": reply})
                            return reply

                    if name == "get_weather":
                        confirmations.append(self._fetch_weather(
                            args.get("date", "today"),
                            args.get("time"),
                            args.get("intent", "summary"),
                        ))
                        continue

                    # SharedMemory 업데이트
                    try:
                        ac = self.shm.get_value("ac")
                        if name == "power_on":
                            ac[0] = AC_POWER_ON
                        elif name == "power_off":
                            ac[0] = AC_POWER_OFF
                        elif name == "set_temperature":
                            ac[1] = int(float(args["temp_c"]))
                        elif name == "set_fan_speed":
                            ac[2] = AC_SPEED.get(args["level"], 0)
                        elif name == "set_mode":
                            ac[3] = AC_MODE.get(args["mode"], 0)
                        elif name == "set_swing":
                            ac[4] = AC_SWING_ON if args["state"] == "on" else AC_SWING_OFF
                        elif name == "set_light":
                            self.shm.set_value("headlight", 1 if args["state"] == "on" else 0)

                        if name != "set_light":
                            self.shm.set_value("ac", ac)
                    except Exception as e:
                        print(f"[LLMProcessor] SharedMemory 업데이트 실패 ({name}): {e}")
                        reply = "장비 제어 중 오류가 발생했어요."
                        self.chat_memory.append({"role": "assistant", "content": reply})
                        return reply

                    confirmations.append(self._confirmation_text(name, args))

                reply = " ".join(confirmations).strip()

            self.chat_memory.append({"role": "assistant", "content": reply})
            if len(self.chat_memory) > self._MAX_MEMORY:
                self.chat_memory = self.chat_memory[-self._MAX_MEMORY:]

            record["reply"] = reply
            self._save_log(record)
            return reply

        except Exception as e:
            print(f"[LLMProcessor] Error: {e}")
            return "오류가 발생했어요. 다시 시도해 주세요."

    # ── 날씨 ──────────────────────────────────────────────────────────────────

    def _fetch_weather(self, date: str, time_str: str | None, intent: str = "summary") -> str:
        now = datetime.now()
        base_date = now.strftime("%Y%m%d")
        base_time = self._TIME_MAP.get(time_str, "1400")

        try:
            r = requests.get(
                "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
                params={
                    "serviceKey": self._KMA_SERVICE_KEY,
                    "numOfRows":  1000,
                    "pageNo":     1,
                    "dataType":   "JSON",
                    "base_date":  base_date,
                    "base_time":  base_time,
                    "nx":         self._DEFAULT_LOCATION["nx"],
                    "ny":         self._DEFAULT_LOCATION["ny"],
                },
                timeout=5,
            )
            r.raise_for_status()
            items = r.json()["response"]["body"]["items"]["item"]
        except Exception:
            return "날씨 정보를 불러오는 데 실패했어요."

        if date not in ["today", "tomorrow"]:
            return "오늘과 내일 날씨만 조회할 수 있어요."

        target = (now + timedelta(days=1) if date == "tomorrow" else now).strftime("%Y%m%d")
        filtered = [i for i in items if i["fcstDate"] == target]
        if not filtered:
            return "해당 날짜의 날씨 정보가 없어요."

        temp = next((i["fcstValue"] for i in filtered if i["category"] == "TMP"), "?")
        sky  = next((i["fcstValue"] for i in filtered if i["category"] == "SKY"), "?")
        pty  = next((i["fcstValue"] for i in filtered if i["category"] == "PTY"), "0")

        sky_map = {"1": "맑음", "3": "구름 많음", "4": "흐림"}
        pty_map = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}

        if intent == "yesno":
            return "네, 강수가 예상돼요." if pty != "0" else "아니요, 강수는 없을 것 같아요."

        pty_str = pty_map.get(pty, "알 수 없음")
        precip = "강수 없음" if pty_str == "없음" else f"강수 형태: {pty_str}"
        return f"기온 {temp}°C, 하늘 {sky_map.get(sky, '알 수 없음')}, {precip}."

    # ── 확인 문장 ─────────────────────────────────────────────────────────────

    def _confirmation_text(self, name: str, args: dict) -> str:
        mode_ko  = {"auto": "자동", "cool": "냉방", "heat": "난방", "fan": "송풍", "dry": "제습"}
        speed_ko = {"auto": "자동", "low": "약", "medium": "중", "high": "강"}
        if name == "power_on":       return "에어컨 전원을 켰어요."
        if name == "power_off":      return "에어컨 전원을 껐어요."
        if name == "set_temperature": return f"에어컨을 {int(float(args['temp_c']))}도로 맞췄어요."
        if name == "set_fan_speed":  return f"바람 세기를 {speed_ko.get(args['level'], args['level'])}으로 설정했어요."
        if name == "set_mode":       return f"모드를 {mode_ko.get(args['mode'], args['mode'])}으로 설정했어요."
        if name == "set_swing":      return "에어 스윙을 켰어요." if args["state"] == "on" else "에어 스윙을 껐어요."
        if name == "set_light":      return "조명을 켰어요." if args["state"] == "on" else "조명을 껐어요."
        return "설정을 적용했어요."

    # ── 로깅 ──────────────────────────────────────────────────────────────────

    def _save_log(self, record: dict):
        with self._JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if not self._CSV_PATH.exists():
            with self._CSV_PATH.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self._CSV_HEADERS)

        with self._CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                record["timestamp"],
                record["session_id"],
                record["user_text"],
                record["reply"],
                json.dumps(record["tool_calls"], ensure_ascii=False),
                record["ok"],
            ])
