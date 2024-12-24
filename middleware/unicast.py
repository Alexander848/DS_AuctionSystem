
import socket
from middleware import MessageType
from middleware import Message
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
        """
        Assume unreliable channels but sensible network configuration (every node
        can be reached from any other node, but packages can be dropped at any time). 
        Assume synchronous communication (upper bounds for message transition times).
        Aim for exactly once semantics: retry + deduplication or retry + idempotency
        of messages. 
        We want at least FIFO channels -> logical timestamps/sequence numbers.
        """
        # TODO retries, deduplication/idempotency
        message: Message = Message(message_type, content, self.ip, self.port)
        target_addr: tuple = (target_ip, target_port)
        self.sendto(str(message).encode("utf-8"), target_addr)

    def receive(self, buffsize: int=1024) -> Message:
        raw: bytes = self.recv(buffsize)
        data: list[str] = raw.decode("utf-8").split(" ")
        message: Message = Message(MessageType(data[0]), data[1], data[2], int(data[3]))
        # TODO send acknowledge back to src
        return message














