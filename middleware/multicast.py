import socket
from middleware import get_my_ip
from middleware import Message
from middleware import MessageType

# multicast settings
IDLE_GRP_IP = '224.1.1.1'
IDLE_GRP_PORT = 5382
MULTICAST_TTL = 2

class MulticastSocket(socket.socket):

    def __init__(self, self_port, group_ip=IDLE_GRP_IP, group_port=IDLE_GRP_PORT, ttl=MULTICAST_TTL):
        print("[middleware/multicast.py] [MulticastSocket.__init__]")
        # multicast
        self.group_ip = group_ip
        self.group_port = group_port
        self.ttl = ttl
        # for respondses with unicast we need to send our own ip and port
        self.ip = get_my_ip()
        self.port = self_port

        super().__init__(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
        self.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, True)
        self.bind((self.group_ip, self.group_port))
        mreq: bytes = socket.inet_aton(self.group_ip) + socket.inet_aton(get_my_ip())
        self.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # overrides parents method
    def send(self, message_type : MessageType, content: str) -> None:
        """
        This functions implements the sending functionality for multicast messages.
        Message consists of 4 parts separated by spaces: MessageType keyword,
        own UUID, ip address and port (to know where to send unicasts answers to).
        """
        print(f"  [middleware/multicast.py] [MulticastSocket.send] {message_type.value} {content} {self.ip} {self.port}")
        message: str = f"{message_type.value} {content} {self.ip} {self.port}"
        self.sendto(message.encode("utf-8"), (self.group_ip, self.group_port))

    def receive(self, buffsize: int=1024) -> Message:
        print(f"  [middleware/multicast.py] [MulticastSocket.receive]")
        raw, adrr = self.recvfrom(buffsize)
        data: list[str] = raw.decode("utf-8").split(" ")
        print(f"  [middleware/multicast.py] [MulticastSocket.receive] {data}")
        return Message(MessageType(data[0]), data[1], data[2], int(data[3]))