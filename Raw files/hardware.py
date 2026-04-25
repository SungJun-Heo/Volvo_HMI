import socket
import threading
import time
import json
import os

# 1. 기본 설정 및 전역 변수
ARDUINO_IP = "10.211.125.127"  # 주기적으로 바뀜, 아두이노 코드 실행 시 IP주소 나옴
PORT = 8888  # 통신 포트 번호
STATUS_FILE = "/home/comfuture/Desktop/bluetooth/volvo-1/status.json"  # status 파일 경로

# 자이로 센서 초기 값과 깊이(현재 작업 깊이)를 임시 저장
latest = {"t1": 0.0, "t2": 0.0, "t3": 0.0, "depth": 0.0}

# 프로그램 종료 시 모든 thread(3개)를 멈추게 하는 스위치
stop = False


# 2. 데이터 수신 thread 1 (아두이노 -> 파이썬): 각도 값 3개와 계산에 따른 깊이 값 1개, 계산은 아두이노에서 함
# 아두이노는 "12.34, 56.78, 90.12, 34.56\n"처럼 값을 보냄. 이를 파이썬은 앞에서부터 theta1,2,3,depth로 인식한다는 코드 구현
def rx_loop(sock: socket.socket):
    global stop  # 전역변수: stop

    # 아두이노에서는 "12.34, 56.78, 90.12, 34.56\n"처럼 한 묶음으로 보내도 파이썬에서 받을 땐 쪼개져서 받을 수 있다.
    # 이를 다시 한 묶음으로 바꿔주는 역할을 함
    f = sock.makefile('r', encoding='utf-8')

    while not stop:
        try:
            line = f.readline()  # 아두이노에서 보낸 한 줄 읽기
            if not line: break  # 연결이 끊기면 즉시 종료

            parts = line.strip().split(",")  # 쉼표를 기준으로 받은 한 줄의 데이터를 쪼개기

            # 아두이노에서 4개의 값(theta1, theta2, theta3, depth)이 정상적으로 들어왔을 때 쪼개 넣기
            if len(parts) >= 4:
                latest["t1"], latest["t2"], latest["t3"], latest["depth"] = map(float, parts[:4])
            # 혹시나 3개의 값만 들어올 경우를 대비한 안전망, 값 3개만 들어가면 depth는 이전 값 유지하고 theta값만 최신화하자
            elif len(parts) == 3:
                latest["t1"], latest["t2"], latest["t3"] = map(float, parts)

        except Exception as e:
            # 통신 노이즈로 데이터가 일시적으로 깨지더라도 멈추지 않고 계속 진행 (중요)
            pass

    stop = True


# 3. 화면 출력 thread2 (터미널에서 상태 확인용), 지금 현재 theta1,2,3와 depth 값을 확인할 수 있다.
def print_loop():
    while not stop:
        # \r 을 사용해 여러 줄로 도배되지 않고, 한 줄 안에서 숫자만 최신화. 즉 덮어쓰기
        print(
            f"\r[LIVE] T1:{latest['t1']:>7.2f} T2:{latest['t2']:>7.2f} T3:{latest['t3']:>7.2f} DEPTH:{latest['depth']:>7.2f}",
            end='', flush=True)
        time.sleep(0.1)  # 0.1초마다 화면 최신화


# 4. JSON 파일 관리 thread3 (status.json <-> 파이썬 <-> 아두이노)
def status_watch_loop(sock: socket.socket):
    global stop
    last_h = None  # 이전 헤드라이트 상태 기억용
    last_f = None  # 이전 팬 속도 상태 기억용

    while not stop:
        try:
            if os.path.exists(STATUS_FILE):
                # (1) 최신 status.json 읽어오기
                with open(STATUS_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)

                aux = data.get("aux", {})

                # (2) 헤드라이트 명령 처리 (상태가 이전과 달라졌을 때만 전송)
                h = aux.get("headlight")
                if h != last_h:
                    sock.sendall(f"{h.upper()}\n".encode())  # 예: "ON\n" 전송
                    last_h = h

                # (3) 팬 속도 명령 처리 (0~4 단계를 PWM 신호 0~255로 변환해서 전송)
                f_speed = aux.get("ac_fan_speed")
                if f_speed is not None and f_speed != last_f:
                    pwm_val = int(f_speed) * 63  # 255/4=63.75, 즉 1단계당 63, 63.75는 소수라 오류 가능성 O
                    sock.sendall(f"FAN:{pwm_val}\n".encode())  # 예: "FAN:255\n" 전송
                    last_f = f_speed

        except Exception as e:
            # 파이썬과 웹 서버가 동시에 파일에 접근해서 충돌이 나면, 에러 뿜지 말고 그냥 이번 턴은 패스
            pass

        time.sleep(0.5)  # 0.5초마다 한 번씩 파일 확인


# 5. 메인 실행부 (thread 총괄)
def main():
    global stop
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        print(f"Connecting to {ARDUINO_IP}...")
        sock.connect((ARDUINO_IP, PORT))  # 아두이노 통신 연결 시도
        print("[CONNECTED]")

        # 위에서 만든 3개의 thread daemon=True로 동시에 실행시킴
        threading.Thread(target=rx_loop, args=(sock,), daemon=True).start()
        threading.Thread(target=print_loop, daemon=True).start()
        threading.Thread(target=status_watch_loop, args=(sock,), daemon=True).start()

        # 메인 프로그램이 바로 꺼지지 않도록 무한 대기 (Ctrl+C 누를 때까지)
        while not stop:
            time.sleep(1)

    except Exception as e:
        print(f"\nError: {e}")

    finally:
        # 에러가 나거나 사용자가 강제 종료 시, 모든 스레드를 정지시키고 소켓 연결을 안전하게 끊음
        stop = True
        sock.close()


# 프로그램 시작점
if __name__ == "__main__":
    main()