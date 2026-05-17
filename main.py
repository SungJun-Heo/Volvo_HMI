import sys
from src import SharedMemory, TCPCommunicator, LLMProcessor, OutputProcessor
from src.STTProcessor import STTProcessor
from src.GUIApp import launch_gui

if __name__ == "__main__":
    shm = SharedMemory()

    tcp    = TCPCommunicator(shm)
    llm    = LLMProcessor(shm)
    output = OutputProcessor(shm)
    stt    = STTProcessor(shm)

    tcp.start()
    llm.start()
    output.start()
    stt.start()

    # GUI runs on the main thread (PyQt6 requirement)
    sys.exit(launch_gui(shm))
