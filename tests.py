
import middleware
import socket
from time import sleep


# used for preliminary, manual testing
def test1() -> None:
    # Local host information
    listen_socket = middleware.setup_broadcast_socket()
    # Bind socket to address and port
    MY_IP = socket.gethostbyname(socket.gethostname())
    listen_socket.bind((MY_IP, middleware.BROADCAST_PORT))
    print("Listening to broadcast messages")
    while True:
        data, addr = listen_socket.recvfrom(1024)
        if data:
            print("Received broadcast message:", data.decode())

def test2() -> None:
    MY_IP = socket.gethostbyname(socket.gethostname())
    sock : socket.socket = middleware.setup_idle_grp_socket(MY_IP)
    middleware.multicast(sock, middleware.Messages.INM.value)


if __name__ == "__main__":
    test2()
    