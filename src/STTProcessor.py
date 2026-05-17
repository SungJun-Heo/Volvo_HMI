"""
STTProcessor - 더미 구현
실제 STT(pyaudio + faster-whisper + porcupine) 연동 시 이 파일을 교체하세요.
"""
import threading
import time


class STTProcessor(threading.Thread):

    def __init__(self, shm, model_size: str = "small"):
        super().__init__(daemon=True)
        self.shm = shm

    def run(self):
        print("[STT] 더미 모드 실행 중 (실제 STT 미연결)")
        while self.shm.is_running:
            triggered = self.shm.stt_trigger.wait(timeout=0.5)
            if triggered and self.shm.is_running:
                self.shm.stt_trigger.clear()
                self._dummy_record()

    def trigger(self):
        self.shm.stt_trigger.set()

    def stop(self):
        self.shm.is_running = False
        self.shm.stt_trigger.set()

    def _dummy_record(self):
        self.shm.stt_active = True
        print("[STT] 더미 녹음 시작 (2초)...")
        time.sleep(2.0)
        self.shm.stt_active = False

        # 더미 텍스트를 llm_input에 쓰고 LLM 트리거
        dummy_text = "에어컨 켜줘"
        print(f"[STT] 더미 결과: {dummy_text}")
        self.shm.llm_input = dummy_text
        self.shm.command_event.set()
