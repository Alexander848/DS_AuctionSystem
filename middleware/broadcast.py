
# This file implements the broadcast.
# NOTE: You probably should be using multicast instead!

import socket


BROADCAST_PORT = 5381


def setup_broadcast_socket() -> socket.socket:
    # Create a UDP socket
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    #broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    return broadcast_socket


def broadcast(sock: socket.socket, message: str, target_ip: str) -> None:
    sock.sendto(str.encode(message), (target_ip, BROADCAST_PORT))












