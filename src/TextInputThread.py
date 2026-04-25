import threading


class TextInputThread(threading.Thread):
    def __init__(self, shm):
        super().__init__(daemon=True)
        self.shm = shm

    def run(self):
        print("[TextInput] 명령을 입력하세요 (종료: Ctrl+C)")
        while self.shm.is_running:
            try:
                text = input("> ").strip()
                if text:
                    self.shm.last_command = text
                    self.shm.command_event.set()
            except EOFError:
                break
