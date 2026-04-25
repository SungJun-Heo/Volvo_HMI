import socket
import time
import random


def start_mock_arduino():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 8888))
    server.listen(1)
    print("가상 아두이노 서버 대기 중 (127.0.0.1:8888)...")

    conn, addr = server.accept()
    print(f"연결됨: {addr}")

    try:
        while True:
            # 1. 클라이언트(PC)가 보낸 제어 명령 수신 (TX 테스트)
            conn.setblocking(False)
            try:
                data = conn.recv(1024)
                if data:
                    print(f" -> [수신된 명령]: {data.decode().strip()}")
            except BlockingIOError:
                pass

            # 2. 클라이언트(PC)에게 센서 데이터 송신 (RX 테스트)
            t1, t2, t3 = random.uniform(0, 90), random.uniform(0, 90), random.uniform(0, 90)
            sensor_data = f"{t1:.2f},{t2:.2f},{t3:.2f}\n"
            conn.sendall(sensor_data.encode())

            time.sleep(1)
    except Exception as e:
        print(f"서버 에러: {e}")
    finally:
        conn.close()
        server.close()


if __name__ == "__main__":
    start_mock_arduino()