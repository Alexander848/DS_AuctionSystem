import multiprocessing
import time
from threading import Thread

import server
from middleware import Message
from middleware import MessageType
from middleware import get_my_ip
from middleware.unicast import UnicastSocket
from middleware.multicast import MulticastSocket
from server import Server


def send_msg_and_wait() -> None:
    socket = UnicastSocket(5900)
    print("socket1: Sending message")
    socket.send(MessageType.TEST, "hello", get_my_ip(), 5901)
    #msg = socket.receive()
    #print(msg)

def receive_msg_and_send() -> None:
    socket = UnicastSocket(5901)
    print("socket2 waits")
    msg = socket.receive()
    #print(msg)


if __name__ == "__main__":
    s2_thread = Thread(target=receive_msg_and_send)
    s1_thread = Thread(target=send_msg_and_wait)
    s2_thread.start()
    time.sleep(1)
    s1_thread.start()