import socket
import threading
import time


class TCPCommunicator(threading.Thread):
    def __init__(self, shm, ip="10.231.238.127", port=8888):
        super().__init__(daemon=True)
        self.shm = shm
        self.ip = ip
        self.port = port
        self.sock = None
        self.last_headlight = None
        self.last_ac = None

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.ip, self.port))
            threading.Thread(target=self._tx_loop, daemon=True).start()
            self._rx_loop()
        except Exception:
            self.shm.is_running = False
        finally:
            self.stop()

    def _rx_loop(self):
        f = self.sock.makefile('r', encoding='utf-8')
        while self.shm.is_running:
            try:
                line = f.readline()
                if not line:
                    break
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    self.shm.set_value("joints", list(map(float, parts[:3])))
                    self.shm.set_value("depth", float(parts[3]))
                elif len(parts) == 3:
                    self.shm.set_value("joints", list(map(float, parts[:3])))
            except Exception:
                pass
        self.stop()

    def _tx_loop(self):
        while self.shm.is_running:
            try:
                headlight = self.shm.get_headlight()
                if headlight != self.last_headlight:
                    self.sock.sendall(f"{headlight}\n".encode())
                    self.last_headlight = headlight

                ac = self.shm.get_ac_state()
                if ac != self.last_ac:
                    pwm_val = int(ac["speed"]) * 63
                    cmd = f"{ac['power']},{ac['temp']},{pwm_val},{ac['mode']},{ac['swing']}\n"
                    self.sock.sendall(cmd.encode())
                    self.last_ac = ac

            except Exception:
                break
            time.sleep(0.5)

    def stop(self):
        self.shm.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
