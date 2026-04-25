import socket
import threading
import time
import random


class DummyArduino:
    _MODE_LABEL  = {0: "auto", 1: "cool", 2: "heat", 3: "fan", 4: "dry"}
    _SWING_LABEL = {0: "off", 1: "on"}

    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self._running = False
        self._conn = None

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(1)
        print(f"[DummyArduino] {self.host}:{self.port} 대기 중...")

        self._conn, addr = server.accept()
        self._running = True
        print(f"[DummyArduino] 연결됨: {addr}\n")

        threading.Thread(target=self._send_joints, daemon=True).start()
        self._receive_commands()

    def _send_joints(self):
        t1 = t2 = t3 = 0.0
        while self._running:
            t1 = round(t1 + random.uniform(-0.5, 0.5), 2)
            t2 = round(t2 + random.uniform(-0.5, 0.5), 2)
            t3 = round(t3 + random.uniform(-0.5, 0.5), 2)
            try:
                self._conn.sendall(f"{t1},{t2},{t3}\n".encode())
            except Exception:
                break
            time.sleep(0.1)

    def _receive_commands(self):
        f = self._conn.makefile("r", encoding="utf-8")
        while self._running:
            try:
                line = f.readline()
                if not line:
                    break
                self._parse_command(line.strip())
            except Exception:
                break
        self._running = False

    def _parse_command(self, line: str):
        parts = line.split(",")

        if len(parts) == 1:
            state = "ON" if parts[0] == "1" else "OFF"
            print(f"[DummyArduino] 조명: {state}")

        elif len(parts) == 5:
            power, temp, pwm, mode, swing = parts
            print(
                f"[DummyArduino] AC | "
                f"power={'ON' if power=='1' else 'OFF'} "
                f"temp={temp}°C "
                f"fan_pwm={pwm} "
                f"mode={self._MODE_LABEL.get(int(mode), mode)} "
                f"swing={self._SWING_LABEL.get(int(swing), swing)}"
            )


if __name__ == "__main__":
    DummyArduino().start()
