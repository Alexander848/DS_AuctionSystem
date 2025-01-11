import time

import server
from middleware import Message
from middleware import MessageType
from middleware import get_my_ip
from middleware.unicast import UnicastSocket
from middleware.multicast import MulticastSocket


# used for preliminary, manual testing
# def test1() -> None:
#     # Local host information
#     listen_socket = middleware.setup_broadcast_socket()
#     # Bind socket to address and port
#     my_ip = socket.gethostbyname(socket.gethostname())
#     listen_socket.bind((my_ip, middleware.BROADCAST_PORT))
#     print("Listening to broadcast messages")
#     while True:
#         data, addr = listen_socket.recvfrom(1024)
#         if data:
#             print("Received broadcast message:", data.decode())


# def test2() -> None:
#     sock: socket.socket = middleware.setup_idle_grp_socket()
#     middleware.multicast(sock, "test message from test2")
#     data, addr = sock.recvfrom(1024)
#     print(data.decode())


# def test3() -> None:
#     for pings in range(10):
#         client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
#         client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
#         client_socket.settimeout(1.0)
#         message = b'test'
#         addr = ("127.0.0.1", 5383)
#
#         start = time.time()
#         client_socket.sendto(message, addr)
#         data, server = client_socket.recvfrom(1024)
#         print(data)
#         try:
#             data, server = client_socket.recvfrom(1024)
#             end = time.time()
#             elapsed = end - start
#             print(f'{data} {pings} {elapsed}')
#         except socket.timeout:
#             print('REQUEST TIMED OUT')


def test_unicast_send_receive() -> None:
    sock: UnicastSocket = UnicastSocket(5385)
    sock.send(MessageType.TEST, "test_unicast", get_my_ip(), 5384)
    msg: Message = sock.receive()
    print(str(msg))

def test_unicast_echo() -> None:
    sock: UnicastSocket = UnicastSocket(5385)
    msg: Message = sock.receive()
    print(str(msg))
    sock.send(MessageType.TEST, "test_unicast", get_my_ip(), 5384)


def test_multicast_send_receive() -> None:
    sock: MulticastSocket = MulticastSocket(5385)
    sock.send(MessageType.TEST, "test_multicast")
    msg: Message = sock.receive()
    print(str(msg))

def test_multicast_echo() -> None:
    sock: MulticastSocket = MulticastSocket(5385)
    msg: Message = sock.receive()
    print(str(msg))
    sock.send(MessageType.TEST, "test_multicast")


def test5() -> None:
    serv1: server.Server = server.Server(5385, set_uuid=1)


if __name__ == "__main__":
    test5()


# paste into cli:
# python -c "import server; server.Server(5384, set_uuid=1)"
# python -c "import server; server.Server(5385, set_uuid=2)"
# python -c "import server; server.Server(5386, set_uuid=3)"

















