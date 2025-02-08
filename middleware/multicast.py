
import random
import socket
import uuid
from queue import Queue
from threading import Thread
from typing import NoReturn
from middleware import get_my_ip
from middleware import Message
from middleware import MessageType

# multicast settings
IDLE_GRP_IP = '224.1.1.1'
IDLE_GRP_PORT = 5382
MULTICAST_TTL = 2

class MulticastSocket(socket.socket):

    def __init__(self, self_port: int, group_ip: str=IDLE_GRP_IP, group_port: int=IDLE_GRP_PORT, ttl: int=MULTICAST_TTL) -> None:
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

        self.dedupe: list[uuid.UUID] = []
        self.received: Queue[Message] = Queue(maxsize=0)       # Used internally by the middleware. Messages might be held back to enforce ordering.
        self.delivered: Queue[Message] = Queue(maxsize=0)      # Used by the server to get messages ready to be processed.

        # using threads to asynchronously receive and deliver messages
        self.thread_receive = Thread(target=self.__receive, name="multicast-receive")
        self.thread_deliver = Thread(target=self.__deliver, name="multicast-deliver")
        self.thread_receive.start()
        self.thread_deliver.start()


    def __receive(self, buffsize: int=1024, network_failure_rate: float=0.0) -> NoReturn:
        """
        This function handles the direct incoming messages. Further message logic goes through the received queue.
        Can simulate network failures by dropping messages with a certain probability (float between 0.0, no failures, to 1.0).
        Unlike Unicast, Multicast does not use explicit acknowledgements.
        """
        while True:
            raw: bytes = self.recv(buffsize)

            # simulate network failure
            if random.random() < network_failure_rate:
                print("Dropped message")
                continue

            data: list[str] = raw.decode("utf-8").split(" ")
            message: Message = Message(MessageType(data[0]), data[1], data[2], int(data[3]), uuid.UUID(data[4]))
            
            # deduplicate messages
            if message.message_id in self.dedupe:
                print("Recieved duplicate message")
                continue

            self.received.put(message)
            #print(f"Received: {message}")

    
    def __deliver(self) -> NoReturn:
        """
        This function will be used to implement FIFO and/or causal ordering.
        Not yet implemented.
        """
        # TODO implement FIFO and causal ordering
        while True:
            message: Message = self.received.get()
            self.delivered.put(message)
            #print(f"Delivered: {message}")


    # overrides parents method
    def send(self, message_type : MessageType, content: str) -> None: # type: ignore
        """
        This functions implements the sending functionality for multicast messages.
        Assume unreliable channels but sensible network configuration (every node
        can be reached from any other node, but packages can be dropped at any time). 
        Assume synchronous communication (upper bounds for message transition times).
        Aim for at most once semantics through deduplication. No explicit acknowledgements
        for multicast messages.
        """
        message: Message = Message(message_type, content, self.ip, self.port, uuid.uuid4())
        self.sendto(str(message).encode("utf-8"), (self.group_ip, self.group_port))



