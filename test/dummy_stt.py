"""STTProcessor 더미 — 마이크 대신 터미널 텍스트 입력을 사용.

main.py 에서 STTProcessor 대신 교체:
    from test.dummy_stt import DummySTTProcessor as STTProcessor
"""
import threading


class DummySTTProcessor(threading.Thread):

    def __init__(self, shm, model_size: str = "small"):
        super().__init__(daemon=True)
        self.shm = shm

    def run(self):
        print("[DummySTT] 텍스트 입력 모드  |  종료: Ctrl+C")
        while self.shm.is_running:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.shm.is_running = False
                break
            if text:
                self.shm.llm_input = text
                self.shm.command_event.set()

    def trigger(self):
        self.shm.stt_trigger.set()

    def stop(self):
        self.shm.is_running = False
        self.shm.stt_trigger.set()
