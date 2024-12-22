
import socket
from middleware import MessageType
from middleware import get_my_ip


class UnicastSocket(socket.socket):
    """
    This class extends the standard socket to perform
    unicast operations for our application.

    example:
    sock: UnicastSocket = middleware.UnicastSocket(5385)
    sock.send(MessageType.TEST, "test message", "192.168.2.103", 5383)
    """

    def __init__(self, port: int) -> None:
        self.ip = get_my_ip()
        self.port = port

        super().__init__(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.bind((self.ip, self.port))

    # overrides parents method
    def send(self, message_type: MessageType, content: str, target_ip: str, target_port: int) -> None:
        message: str = f"{message_type.value} {content} {self.ip} {self.port}"
        target_addr: tuple = (target_ip, target_port)
        self.sendto(message.encode("utf-8"), target_addr)













