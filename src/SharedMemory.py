import threading

class SharedMemory:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = True
        self.command_event = threading.Event()
        self.last_command = ""
        self.status = {
            "headlight": 0,
            "ac": [0, 24, 0, 0, 0],  # power, temp, speed, mode, swing
            "joints": [0.0, 0.0, 0.0],
            "depth": 0.0
        }

    def set_value(self,key,value):
        with self.lock:
            self.status[key] = value
    def get_value(self,key,default = None):
        with self.lock:
            return self.status.get(key,default)
    def get_all(self):
        with self.lock:
            return self.status.copy()