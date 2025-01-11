
import socket
import select
import time
from os import MFD_ALLOW_SEALING

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
        self.message_id_counter = 1

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
        Ack message is the sent message send back.
        """
        ack_buffsize = 1024; ack_timeout = 0.5; message_retries = 10
        self.message_id_counter += 1
        message_id = self.message_id_counter

        while message_retries > 0:
            message_retries -= 1

            # Send Message
            message: Message = Message(message_type, content, self.ip, self.port, message_id)
            target_addr: tuple = (target_ip, target_port)
            self.sendto(str(message).encode("utf-8"), target_addr)

            # Wait for Ack or Timeout
            t_timeout = time.time() + ack_timeout
            while time.time() < t_timeout:
                ready = select.select([self], [], [], ack_timeout / 10)
                if ready[0]:
                    raw: bytes = self.recv(ack_buffsize)
                    data: list[str] = raw.decode("utf-8").split(" ")
                    ack_message: Message = Message(MessageType(data[0]), data[1], data[2], int(data[3]), int(data[4]))
                    # check if this is the right message
                    if (ack_message.message_type == MessageType.UNICAST_ACK and ack_message.src_ip == get_my_ip() and
                            ack_message.src_port == self.port and ack_message.message_id == message_id):
                        # Correct Ack received, exit function
                        return


        # throw an error. Couldn't reach receiver TODO errorhandling


    # Catches incoming messages and answers Unicast_Ack message, ignores incoming Unicast_Ack messages
    def receive(self, buffsize: int=1024) -> Message:
        while True:
            raw: bytes = self.recv(buffsize)
            data: list[str] = raw.decode("utf-8").split(" ")
            message: Message = Message(MessageType(data[0]), data[1], data[2], int(data[3]), int(data[4]))

            # Ignore Unicast_Ack messages
            if message.message_type is not MessageType.UNICAST_ACK :
                # send acknowledgement back to sender
                message.message_type = MessageType.UNICAST_ACK
                self.sendto(str(message).encode("utf-8"), (message.src_ip, message.src_port))
                break

        return message
















