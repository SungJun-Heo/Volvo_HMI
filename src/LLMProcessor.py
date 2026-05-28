from __future__ import annotations
import os
import json
import threading
from dotenv import load_dotenv
from openai import OpenAI
from .constants import TOOLS, MAX_MEMORY

load_dotenv()


class LLMProcessor(threading.Thread):

    def __init__(self, shm, base_url=None, model="volvo_qwen_hmi"):
        super().__init__(daemon=True)
        self.shm = shm
        self.model = model
        base_url = base_url or os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.chat_memory = []

    def run(self):
        if not self._ping():
            self.shm.is_running = False
            return
        while self.shm.is_running:
            self.shm.command_event.wait()
            text = self.shm.llm_input
            self.shm.command_event.clear()
            if text:
                self.shm.llm_processing = True
                output = self._call_llm(text)
                self.shm.llm_output = output
                self.shm.llm_processing = False

    def stop(self):
        self.shm.is_running = False
        self.shm.command_event.set()

    def _ping(self) -> bool:
        try:
            print("[LLM] 서버 연결 확인 중...")
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            print("[LLM] 서버 연결 성공")
            return True
        except Exception as e:
            print(f"[LLM] 서버 연결 실패: {e}")
            return False

    def _call_llm(self, text: str) -> list | str:
        self.chat_memory.append({"role": "user", "content": text})
        messages = self.chat_memory

        try:
            print(f"[LLM →] \"{text}\"")
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                # 1. LLM이 도구를 호출했다는 사실을 기억에 저장
                self.chat_memory.append(msg.model_dump(exclude_unset=True))
                
                is_read_tool = False
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments or "{}")

                    if name == "get_arm_status":
                        is_read_tool = True
                        
                        # SharedMemory에서 실제 센서값 읽어오기
                        joints = self.shm.get_value("joints")
                        depth = self.shm.get_value("depth")
                        
                        # LLM에게 제공할 가이드라인 텍스트
                        tool_result = f"현재 굴착기 암 조인트 각도: {joints}, 버켓 깊이: {depth}m. 이 수치를 안내해주고, 이 기능이 사용자에게 어떤 도움을 줄 수 있는지 신기능 사용법을 자연스럽고 친절하게 설명해줘."
                        
                        self.chat_memory.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": name,
                            "content": tool_result
                        })
                    else:
                        # SharedMemory를 직접 수정하여 아두이노와 GUI에 즉각 반영
                        try:
                            if name == "power_on":
                                self.shm.set_ac_power("on")
                            elif name == "power_off":
                                self.shm.set_ac_power("off")
                            elif name == "set_temperature":
                                self.shm.set_ac_temperature(args.get("temp_c"))
                            elif name == "set_fan_speed":
                                self.shm.set_ac_fan_speed(args.get("level"))
                            elif name == "set_mode":
                                self.shm.set_ac_mode(args.get("mode"))
                            elif name == "set_swing":
                                self.shm.set_ac_swing(args.get("state"))
                            elif name == "set_light":
                                self.shm.set_headlight(args.get("state"))

                            # 성공적으로 제어했음을 LLM 기억에 저장
                            self.chat_memory.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": name,
                                "content": "success"
                            })
                        except Exception as e:
                            print(f"[LLMProcessor] 하드웨어 제어 실패 ({name}): {e}")
                            self.chat_memory.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": name,
                                "content": f"error: {e}"
                            })

                if is_read_tool:
                    # 2. 데이터를 얻은 LLM에게 다시 사람의 말로 설명해달라고 2차 호출
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.chat_memory
                    resp2 = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.3,
                        top_p=0.1,
                        extra_body={"options": {"repeat_penalty": 1.15, "num_ctx": 2048}},
                    )
                    final_msg = resp2.choices[0].message
                    output = (final_msg.content or "").strip()
                else:
                    # 3. 기존 하드웨어 제어 명령 반환
                    output = [
                        {"name": tc.function.name, "args": json.loads(tc.function.arguments or "{}")}
                        for tc in msg.tool_calls
                    ]
            else:
                output = (msg.content or "").strip()

            print(f"[LLM ←] {output}")

            # 메모리 오염 방지: 제어 명령은 깔끔한 문장으로 대체 저장
            if isinstance(output, str):
                self.chat_memory.append({"role": "assistant", "content": output})
            else:
                self.chat_memory.append({"role": "assistant", "content": "하드웨어 제어 명령을 실행했습니다."})
                
            if len(self.chat_memory) > MAX_MEMORY:
                self.chat_memory = self.chat_memory[-MAX_MEMORY:]

            return output

        except Exception as e:
            print(f"[LLM] 오류: {e}")
            return ""
