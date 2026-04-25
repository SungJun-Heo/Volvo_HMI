import time
from src import SharedMemory, TCPCommunicator, LLMProcessor
from src.TextInputThread import TextInputThread

if __name__ == "__main__":
    shm = SharedMemory()

    tcp   = TCPCommunicator(shm)
    llm   = LLMProcessor(shm)
    text  = TextInputThread(shm)

    tcp.start()
    llm.start()
    text.start()

    try:
        while shm.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n종료 중...")
    finally:
        tcp.stop()
        llm.stop()
