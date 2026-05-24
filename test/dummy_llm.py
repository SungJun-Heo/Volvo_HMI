"""LLMProcessor 더미 — LLM API 없이 tool_calls 또는 텍스트를 수동으로 주입.

main.py 에서 LLMProcessor 대신 교체:
    from test.dummy_llm import DummyLLMProcessor
    llm = DummyLLMProcessor(shm)
"""
import json
import threading

# (key, cast, 프롬프트, optional)
_P = lambda k, t, p, o=False: (k, t, p, o)

_TOOLS = [
    ("power_on",        [],  "에어컨 켜기"),
    ("power_off",       [],  "에어컨 끄기"),
    ("set_temperature", [_P("temp_c", float, "온도 (16-30)")],                          "온도 설정"),
    ("set_fan_speed",   [_P("level",  str,   "풍속 [low/medium/high/auto]")],           "풍속 설정"),
    ("set_mode",        [_P("mode",   str,   "모드 [cool/heat/fan/auto/dry]")],         "모드 설정"),
    ("set_swing",       [_P("state",  str,   "스윙 [on/off]")],                         "스윙 설정"),
    ("set_light",       [_P("state",  str,   "조명 [on/off]")],                         "조명 설정"),
    ("get_weather",     [_P("date",   str,   "날짜 [today/tomorrow]"),
                         _P("time",   str,   "시간 [morning/afternoon/evening/night] (엔터=생략)", True),
                         _P("intent", str,   "의도 [summary/yesno] (엔터=생략)", True)], "날씨 조회"),
    ("(텍스트 응답)",   [],  "도구 없이 텍스트만 반환"),
]

_TEXT_IDX = len(_TOOLS) - 1


class DummyLLMProcessor(threading.Thread):
    """LLMProcessor 인터페이스를 유지하면서 API 대신 터미널 입력을 사용."""

    def __init__(self, shm):
        super().__init__(daemon=True)
        self.shm = shm

    def run(self):
        print("[DummyLLM] 수동 입력 모드  |  종료: Ctrl+C\n")
        while self.shm.is_running:
            self.shm.command_event.wait()
            self.shm.command_event.clear()
            if not self.shm.is_running:
                break

            print(f"\n[DummyLLM] 입력된 명령: \"{self.shm.llm_input}\"")
            output = self._prompt_output()
            if output is not None:
                self.shm.llm_output = output

    def stop(self):
        self.shm.is_running = False
        self.shm.command_event.set()

    def _prompt_output(self):
        print("─" * 44)
        for i, (name, _, desc) in enumerate(_TOOLS, 1):
            print(f"  {i}. {name:<22} {desc}")
        print()

        try:
            raw = input("번호 선택 (엔터=건너뜀): ").strip()
        except (EOFError, KeyboardInterrupt):
            self.shm.is_running = False
            return None

        if not raw:
            return None

        try:
            idx = int(raw) - 1
        except ValueError:
            print("숫자를 입력하세요.")
            return None

        if not (0 <= idx < len(_TOOLS)):
            print("범위를 벗어났습니다.")
            return None

        if idx == _TEXT_IDX:
            return self._prompt_text()

        return self._prompt_tool_call(idx)

    def _prompt_tool_call(self, idx: int):
        tool_name, params, _ = _TOOLS[idx]
        args: dict = {}

        for key, cast, prompt, optional in params:
            try:
                val = input(f"  {prompt}: ").strip()
            except (EOFError, KeyboardInterrupt):
                self.shm.is_running = False
                return None

            if not val:
                if optional:
                    continue
                print("  필수 값입니다.")
                return None

            try:
                args[key] = cast(val)
            except ValueError:
                print(f"  형식 오류: '{val}'")
                return None

        call = [{"name": tool_name, "args": args}]
        print(f"[DummyLLM ←] {json.dumps(call, ensure_ascii=False)}")
        return call

    def _prompt_text(self):
        try:
            text = input("  텍스트 응답 내용: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.shm.is_running = False
            return None
        print(f"[DummyLLM ←] \"{text}\"")
        return text
