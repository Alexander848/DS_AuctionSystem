
import middleware
import socket
import time

import server


# used for preliminary, manual testing
def test1() -> None:
    # Local host information
    listen_socket = middleware.setup_broadcast_socket()
    # Bind socket to address and port
    my_ip = socket.gethostbyname(socket.gethostname())
    listen_socket.bind((my_ip, middleware.BROADCAST_PORT))
    print("Listening to broadcast messages")
    while True:
        data, addr = listen_socket.recvfrom(1024)
        if data:
            print("Received broadcast message:", data.decode())


def test2() -> None:
    sock: socket.socket = middleware.setup_idle_grp_socket()
    middleware.multicast(sock, "test message from test2")
    data, addr = sock.recvfrom(1024)
    print(data.decode())


def test3() -> None:
    for pings in range(10):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
        client_socket.settimeout(1.0)
        message = b'test'
        addr = ("127.0.0.1", 5383)

        start = time.time()
        client_socket.sendto(message, addr)
        data, server = client_socket.recvfrom(1024)
        print(data)
        try:
            data, server = client_socket.recvfrom(1024)
            end = time.time()
            elapsed = end - start
            print(f'{data} {pings} {elapsed}')
        except socket.timeout:
            print('REQUEST TIMED OUT')


def test4() -> None:
    sock: socket.socket = middleware.setup_unicast_socket(5385)
    middleware.unicast(sock, "test message from test4", (middleware.get_my_ip(), 5385))
    data, addr = sock.recvfrom(1024)
    print(data.decode())


def test5() -> None:
    serv1: server.Server = server.Server(5385)


if __name__ == "__main__":
    test5()



















