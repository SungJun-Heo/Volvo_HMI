import socket
import threading
import time
from .constants import AC_IDX_POWER, AC_IDX_TEMP, AC_IDX_SPEED, AC_IDX_MODE, AC_IDX_SWING


class TCPCommunicator(threading.Thread):
    def __init__(self, shm, ip="127.0.0.1", port=8888):
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
                self.shm.set_value("joints", list(map(float, parts[:3])))
            except Exception:
                pass
        self.stop()

    def _tx_loop(self):
        while self.shm.is_running:
            try:
                status = self.shm.get_all()

                current_headlight = status.get("headlight")
                if current_headlight != self.last_headlight and current_headlight is not None:
                    cmd = f"{current_headlight}\n"
                    self.sock.sendall(cmd.encode())
                    self.last_headlight = current_headlight

                current_ac = status.get("ac")
                if current_ac != self.last_ac and current_ac is not None:
                    pwm_val = int(current_ac[AC_IDX_SPEED]) * 63
                    cmd = (f"{current_ac[AC_IDX_POWER]},{current_ac[AC_IDX_TEMP]},"
                           f"{pwm_val},{current_ac[AC_IDX_MODE]},{current_ac[AC_IDX_SWING]}\n")
                    self.sock.sendall(cmd.encode())
                    self.last_ac = current_ac.copy()

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