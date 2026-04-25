'''
self.status = {
            "headlight": 0,
            "ac" : [0, 24, 0], # power, temperature, speed
            "joints": [0.0,0.0,0.0],
            "depth" : 0.0
        }
'''

from src.SharedMemory import *

shm = SharedMemory()

shm.set_value("headlight", 3)
shm.set_value("ac", [1, 21, 3])
print(shm.get_value("depth"))
print(shm.get_all())
