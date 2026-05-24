import os
import json
import threading
from dotenv import load_dotenv
from openai import OpenAI
from .constants import SYSTEM_PROMPT, TOOLS, MAX_MEMORY

load_dotenv()


class LLMProcessor(threading.Thread):

    def __init__(self, shm, base_url=None, model="volvo_qwen"):
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
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.chat_memory

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
                output = [
                    {"name": tc.function.name, "args": json.loads(tc.function.arguments or "{}")}
                    for tc in msg.tool_calls
                ]
            else:
                output = (msg.content or "").strip()

            print(f"[LLM ←] {output}")

            self.chat_memory.append({"role": "assistant", "content": str(output)})
            if len(self.chat_memory) > MAX_MEMORY:
                self.chat_memory = self.chat_memory[-MAX_MEMORY:]

            return output

        except Exception as e:
            print(f"[LLM] 오류: {e}")
            return ""
