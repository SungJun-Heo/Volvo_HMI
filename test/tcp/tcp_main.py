import threading
import time
from src.TCPCommunicator import *
from src.SharedMemory import *
if __name__ == "__main__":
    shared_mem = SharedMemory()

    # 로컬 테스트를 위해 IP를 127.0.0.1로 설정
    client = TCPCommunicator(shared_mem, ip="127.0.0.1", port=8888)
    client.start()

    try:
        count = 0
        while shared_mem.is_running:
            # 1. 송신 테스트: 2초마다 전등과 에어컨 상태 변경
            if count % 2 == 0:
                shared_mem.set_value("headlight", 1 if (count // 2) % 2 == 0 else 0)
                shared_mem.set_value("ac", [1, 22, 2 if count % 4 == 0 else 1])

            # 2. 수신 확인: 수신 루프가 업데이트한 joints 값 출력
            current_status = shared_mem.get_all()
            print(f"[LOG] Joints: {current_status['joints']} | HL: {current_status['headlight']} | AC: {current_status['ac']}")

            count += 1
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n테스트 종료 중...")
    finally:
        client.stop()