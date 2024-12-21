

# implements communication
# heartbeat
# detect failures


import socket
from enum import Enum


class Messages(Enum):
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"         # unicast to send UUID
    INM_ANSWER = "INM_ANSWER"                  # INM response to get INM address


BROADCAST_PORT = 5381
# multicast settings
IDLE_GRP_IP = '224.1.1.1'
IDLE_GRP_PORT = 5382
MULTICAST_TTL = 2


def get_my_ip() -> str:
    # defaults to 127.0.0.1 for me. workaround: hardcode IP
    #return socket.gethostbyname(socket.gethostname())
    return "192.168.0.111"     # override IP


def setup_broadcast_socket() -> socket.socket:
    # Create a UDP socket
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    #broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    return broadcast_socket


def broadcast(sock: socket.socket, message: str, target_ip: str) -> None:
    sock.sendto(str.encode(message), (target_ip, BROADCAST_PORT))


def setup_idle_grp_socket() -> socket.socket:
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL) 
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, True)
    sock.bind((IDLE_GRP_IP, IDLE_GRP_PORT))
    mreq: bytes = socket.inet_aton(IDLE_GRP_IP) + socket.inet_aton(get_my_ip())
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


def multicast(sock: socket.socket, message: str) -> None:
    sock.sendto(message.encode("utf-8"), (IDLE_GRP_IP, IDLE_GRP_PORT))



class UnicastSocket(socket.socket):

    def __init__(self, port: int) -> None:
        self.ip = get_my_ip()
        self.port = port

        super().__init__(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.bind((self.ip, self.port))
    

    def send(self, message_type: Messages, content: str, target_ip: str, target_port: int) -> None:
        message: str = f"{message_type.value} {content} {self.ip} {self.port}"
        target_addr: tuple = (target_ip, target_port)
        self.sendto(message.encode("utf-8"), target_addr)


















