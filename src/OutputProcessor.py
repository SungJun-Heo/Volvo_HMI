import time
import threading
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from .constants import TIME_MAP, DEFAULT_LOCATION

load_dotenv()

import os
_KMA_SERVICE_KEY = os.getenv("KMA_SERVICE_KEY", "")


class OutputProcessor(threading.Thread):

    def __init__(self, shm):
        super().__init__(daemon=True)
        self.shm = shm

    def run(self):
        while self.shm.is_running:
            output = self.shm.llm_output
            if output is not None:
                if isinstance(output, list):
                    self._apply_tools(output)
                elif isinstance(output, str) and output:
                    print(f"[Output] {output}")  # TODO: TTS 연결
                self.shm.llm_output = None
            time.sleep(0.1)

    def stop(self):
        self.shm.is_running = False

    # ── tool 처리 ──────────────────────────────────────────────────────────────

    def _apply_tools(self, tool_calls: list):
        for call in tool_calls:
            name = call["name"]
            args = call["args"]
            try:
                if name == "power_on":
                    self.shm.set_ac_power("on")
                elif name == "power_off":
                    self.shm.set_ac_power("off")
                elif name == "set_temperature":
                    self.shm.set_ac_temperature(int(float(args["temp_c"])))
                elif name == "set_fan_speed":
                    self.shm.set_ac_fan_speed(args["level"])
                elif name == "set_mode":
                    self.shm.set_ac_mode(args["mode"])
                elif name == "set_swing":
                    self.shm.set_ac_swing(args["state"])
                elif name == "set_light":
                    self.shm.set_headlight(args["state"])
                elif name == "get_weather":
                    result = self._fetch_weather(
                        args.get("date", "today"),
                        args.get("time"),
                        args.get("intent", "summary"),
                    )
                    print(f"[Weather] {result}")  # TODO: TTS 연결
            except Exception as e:
                print(f"[OutputProcessor] 처리 실패 ({name}): {e}")

    # ── 날씨 ──────────────────────────────────────────────────────────────────

    def _fetch_weather(self, date: str, time_str: str | None, intent: str = "summary") -> str:
        now = datetime.now()
        base_date = now.strftime("%Y%m%d")
        base_time = TIME_MAP.get(time_str, "1400")

        try:
            r = requests.get(
                "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
                params={
                    "serviceKey": _KMA_SERVICE_KEY,
                    "numOfRows":  1000,
                    "pageNo":     1,
                    "dataType":   "JSON",
                    "base_date":  base_date,
                    "base_time":  base_time,
                    "nx":         DEFAULT_LOCATION["nx"],
                    "ny":         DEFAULT_LOCATION["ny"],
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
