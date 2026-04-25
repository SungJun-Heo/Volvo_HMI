import socket

# 로컬 컴퓨터 내부에서만 통신하므로 IP를 '127.0.0.1'(localhost)로 설정합니다.
HOST = '127.0.0.1'
PORT = 8888

# 1. 소켓 생성 (출입문 만들기)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2. 바인딩 및 리슨 (주소를 할당하고 손님을 기다림)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"[서버] {HOST}:{PORT}에서 클라이언트의 접속을 기다리는 중...")

# 3. 연결 수락 (★ 클라이언트가 올 때까지 여기서 프로그램이 멈춰서 기다립니다!)
client_socket, addr = server_socket.accept()
print(f"[서버] 클라이언트가 연결되었습니다! 주소: {addr}")

try:
    while True:
        # 4. 데이터 수신 (★ 데이터가 올 때까지 기다립니다)
        data = client_socket.recv(1024)

        # 빈 데이터가 오면 클라이언트가 연결을 끊었다는 뜻입니다.
        if not data:
            print("[서버] 클라이언트가 연결을 종료했습니다.")
            break

        message = data.decode('utf-8')
        print(f"[서버] 📥 수신: {message}")

        # 5. 데이터 응답 (받은 메시지에 답장을 붙여서 다시 보냄)
        reply = f"서버가 '{message}'를 잘 받았습니다!\n"
        client_socket.sendall(reply.encode('utf-8'))
        print(f"[서버] 📤 답장 전송 완료")

finally:
    # 6. 통신이 끝나면 소켓을 닫아줍니다.
    client_socket.close()
    server_socket.close()
    print("[서버] 시스템 종료")