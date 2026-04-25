import socket
import time

HOST = '127.0.0.1'
PORT = 8888

# 1. 소켓 생성
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print(f"[클라이언트] {HOST}:{PORT} 서버로 연결 시도 중...")

try:
    # 2. 연결 요청 (서버가 켜져 있어야 성공합니다)
    client_socket.connect((HOST, PORT))
    print("[클라이언트] 서버와 연결 성공!\n")

    for i in range(1, 20):
        # 3. 데이터 송신
        msg = f"안녕하세요, {i}번째 메시지입니다."
        client_socket.sendall(msg.encode('utf-8'))
        print(f"[클라이언트] 📤 전송: {msg}")

        # 4. 데이터 수신 대기 (서버의 답장을 기다림)
        data = client_socket.recv(1024)
        print(f"[클라이언트] 📥 수신: {data.decode('utf-8')}\n")

        time.sleep(1) # 1초 대기

finally:
    # 5. 통신 종료
    client_socket.close()
    print("[클라이언트] 시스템 종료")