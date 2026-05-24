"""
GUI 단독 테스트 스크립트
TCP / LLM 서버 없이 GUI 동작을 확인합니다.

실행:
    python test/test_gui.py
"""
import sys
import math
import threading
import time
import random

sys.path.insert(0, ".")   # 프로젝트 루트에서 실행

from src.SharedMemory import SharedMemory
from src.STTProcessor import STTProcessor
from src.GUIApp import launch_gui


def simulate_joints(shm: SharedMemory):
    """관절 각도를 부드럽게 변화시켜 2D 다이어그램 애니메이션 확인."""
    t = 0.0
    while shm.is_running:
        j0 = 40.0 + 20.0 * math.sin(t * 0.3)
        j1 = -75.0 + 15.0 * math.sin(t * 0.5 + 1.0)
        j2 = -25.0 + 10.0 * math.sin(t * 0.7 + 2.0)
        shm.set_value("joints", [j0, j1, j2])
        t += 0.1
        time.sleep(0.1)


if __name__ == "__main__":
    shm = SharedMemory()

    # 관절 시뮬레이션 스레드
    sim = threading.Thread(target=simulate_joints, args=(shm,), daemon=True)
    sim.start()

    # STT (더미 모드)
    stt = STTProcessor(shm)
    stt.start()

    print("=== GUI 테스트 시작 ===")
    print("- 2D 굴착기 다이어그램: 관절이 자동으로 움직입니다")
    print("- 음성 입력 버튼: 클릭하면 2초 후 더미 텍스트가 표시됩니다")
    print("- AC / 헤드라이트: 버튼으로 직접 제어 테스트")
    print("- 창 닫기로 종료")

    sys.exit(launch_gui(shm))
