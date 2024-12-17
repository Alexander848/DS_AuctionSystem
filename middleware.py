

# implements communication
# heartbeat
# detect failures


import socket


BROADCAST_PORT = 5972

def setup_broadcast_socket() -> socket.socket:
    # Create a UDP socket
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
    return broadcast_socket

def broadcast(socket : socket.socket, message : str, ip : str) -> None:
    socket.sendto(str.encode(message), (ip, BROADCAST_PORT))


