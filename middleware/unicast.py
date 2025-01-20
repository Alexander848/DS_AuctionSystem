
import random
import socket
import time
import uuid
from typing import NoReturn
from queue import Queue

from middleware import MessageType
from middleware import Message
from middleware import get_my_ip

from threading import Thread



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

        self.wait_acknowledge: list[uuid.UUID] = []
        self.dedupe: list[uuid.UUID] = []
        self.received: Queue[Message] = Queue(maxsize=0)       # Used internally by the middleware. Messages might be held back to enforce ordering.
        self.delivered: Queue[Message] = Queue(maxsize=0)      # Used by the server to get messages ready to be processed.

        # using threads to asynchronously receive and deliver messages
        self.thread_receive = Thread(target=self.__receive)
        self.thread_deliver = Thread(target=self.__deliver)
        self.thread_receive.start()
        self.thread_deliver.start()


    def __receive(self, buffsize: int=1024, network_failure_rate: float=0.0) -> NoReturn:
        """
        This function handles the direct incoming messages. Further message logic goes through the received queue.
        Can simulate network failures by dropping messages with a certain probability (float between 0.0, no failures, to 1.0).
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
            
            # handle acks
            if message.message_type is MessageType.UNICAST_ACK:
                #print(f"Received ack: {message}")
                self.wait_acknowledge.append(message.message_id)
                continue

            self.received.put(message)
            #print(f"Received: {message}")
            # send ack back
            ack_message: Message = Message(MessageType.UNICAST_ACK, "", self.ip, self.port, message.message_id)
            #print(f"Sending Ack: {ack_message}")
            self.sendto(str(ack_message).encode("utf-8"), (message.src_ip, message.src_port))

    
    def __deliver(self) -> NoReturn:
        """
        This function will be used to implement FIFO channels.
        Not yet implemented.
        """
        # TODO implement FIFO channels
        while True:
            message: Message = self.received.get()
            self.delivered.put(message)
            #print(f"Delivered: {message}")


    def __thread_send(self, message_type: MessageType, content: str, target_ip: str, target_port: int, ack_timeout: float, message_retries: int) -> None:
        """
        This function is used for sending threads to asynchronously send messages and await the respective ack.
        """
        message_uuid: uuid.UUID = uuid.uuid4()
        while message_retries > 0:
            message_retries -= 1
            message: Message = Message(message_type, content, self.ip, self.port, message_uuid)
            target_addr: tuple[str, int] = (target_ip, target_port)
            #print(f"Sending: {message}")
            self.sendto(str(message).encode("utf-8"), target_addr)

            # handle ack
            time.sleep(ack_timeout)
            if message.message_id in self.wait_acknowledge:
                # correct Ack received, exit function
                self.wait_acknowledge.remove(message.message_id)
                return
        # no ack after 3 trys: throw an error. Couldn't reach receiver TODO errorhandling


    # overrides parents method
    def send(self, message_type: MessageType, content: str, target_ip: str, target_port: int) -> None: # type: ignore
        """
        Assume unreliable channels but sensible network configuration (every node
        can be reached from any other node, but packages can be dropped at any time). 
        Assume synchronous communication (upper bounds for message transition times).
        Aim for exactly once semantics: retry + deduplication or retry + idempotency
        of messages. 
        We want at least FIFO channels -> logical timestamps/sequence numbers.
        Ack message is the sent message send back.
        """
        # TODO fifo
        ack_timeout: float = 0.5
        message_retries: int = 3
        sending_thread: Thread = Thread(target=self.__thread_send, args=(message_type, content, target_ip, target_port, ack_timeout, message_retries))
        sending_thread.start()

