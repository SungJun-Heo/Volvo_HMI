import sys
import argparse

from src.SharedMemory import SharedMemory
from src.OutputProcessor import OutputProcessor
from src.TCPCommunicator import TCPCommunicator
from src.GUIApp import launch_gui


def parse_args():
    p = argparse.ArgumentParser(description="Volvo HMI")
    p.add_argument("--dummy-stt",    action="store_true",    help="STTProcessor 대신 DummySTTProcessor 사용")
    p.add_argument("--dummy-llm",    action="store_true",    help="LLMProcessor 대신 DummyLLMProcessor 사용")
    p.add_argument("--tcp-address",  default="127.0.0.1:8888", metavar="HOST:PORT")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    tcp_host, tcp_port = args.tcp_address.rsplit(":", 1)

    shm = SharedMemory()

    if args.dummy_stt:
        from test.dummy_stt import DummySTTProcessor
        stt = DummySTTProcessor(shm)
    else:
        from src.STTProcessor import STTProcessor
        stt = STTProcessor(shm)

    if args.dummy_llm:
        from test.dummy_llm import DummyLLMProcessor
        llm = DummyLLMProcessor(shm)
    else:
        from src.LLMProcessor import LLMProcessor
        llm = LLMProcessor(shm)

    tcp    = TCPCommunicator(shm, ip=tcp_host, port=int(tcp_port))
    output = OutputProcessor(shm)

    tcp.start()
    llm.start()
    output.start()
    stt.start()

    # GUI runs on the main thread (PyQt6 requirement)
    sys.exit(launch_gui(shm))
