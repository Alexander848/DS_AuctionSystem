

# implements communication
# heartbeat
# detect failures


import socket
from enum import Enum


class Messages(Enum):
    #DISCOVERY = "DISCOVERY"     # multicast for discovery
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"         # unicast to send UUID
    INM = "INM"                         # INM response to get INM address


BROADCAST_PORT = 5381
# multicast settings
IDLE_GRP_IP = '224.1.1.1'
IDLE_GRP_PORT = 5382
MULTICAST_TTL = 2


def setup_broadcast_socket() -> socket.socket:
    # Create a UDP socket
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    #broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    return broadcast_socket


def broadcast(socket : socket.socket, message : str, target_ip : str) -> None:
    socket.sendto(str.encode(message), (target_ip, BROADCAST_PORT))


def setup_idle_grp_socket(my_ip : str) -> socket.socket:
    sock : socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL) 
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, True)
    #sock.bind((IDLE_GRP_IP, IDLE_GRP_PORT))
    sock.bind(("", IDLE_GRP_PORT))
    mreq = socket.inet_aton(IDLE_GRP_IP) + socket.inet_aton(my_ip)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


def multicast(sock : socket.socket, message : str) -> None:
    sock.sendto(message.encode("utf-8"), (IDLE_GRP_IP, IDLE_GRP_PORT))


def setup_unicast_socket(port: int) -> socket.socket:
    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.bind((get_my_ip(), port))
    return sock


def unicast(sock: socket.socket, message_type: Messages, content: str, own_ip: str, own_port: int, target_ip: str, target_port: int) -> None:
    message: str = f"{message_type.value} {content} {own_ip} {own_port}"
    target_addr: tuple = (target_ip, target_port)
    sock.sendto(message.encode("utf-8"), target_addr)



















