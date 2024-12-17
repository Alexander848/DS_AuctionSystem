
import middleware
import socket


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



if __name__ == "__main__":
    test1()
    