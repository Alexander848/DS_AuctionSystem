

# every server:
# uid management
# dynamic discovery
# join pool of idle nodes
# LCR

# for INM:
# start auction
# middleware detects crashes -> repair ring, re-election

# active auctioneer node aan:
# manage auction
# replicate to passive auctioneer nodes pan
# finalize auction

# passive auctioneer node pan:
# detect aan failures, re-elect


import uuid
from enum import Enum
import socket
import time
import select

from middleware import Message
from middleware import MessageType
from middleware import get_my_ip
from middleware.multicast import MulticastSocket
from middleware.unicast import UnicastSocket


class Server:
    class State(Enum):
        UNINITIALIZED = 0
        INITIALIZING = 1
        IDLE = 2
        INM = 3
        AAN = 4
        PAN = 5

    def __init__(self, port=5384) -> None:
        self.port = port        # we need to make sure the port is unique for each IP address. TODO: how?
        self.ip = get_my_ip()

        self.UUID: uuid.UUID = uuid.uuid4()     # generates a new UUID every time
        self.state: Server.State = Server.State.UNINITIALIZED
        
        #self.broadcast_sock: socket.socket = middleware.setup_broadcast_socket()
        self.idle_grp_sock: MulticastSocket = MulticastSocket(self.port)
        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)
        
        self.inm: tuple[str, int] = ("", -1) 
        #self.neighbor = None

        self.main()

    def main(self) -> None:
        self.dynamic_discovery()
        while True:
            self.message_parser()

    def __str__(self) -> str:
        return f"Server: {self.UUID=} {self.state=}"

    def collect_responses(self, timeout: float=3.0) -> list[Message]:
        """
        Collects responses from a both the multicast and the 
        unicast socket for a given amount of time.

        Example:
        responses : list[str] = self.collect_responses(1.0)
        """
        start_time: float = time.time()
        responses: list[Message] = []

        while time.time() - start_time < timeout:
            # select will block until one of the following conditions are met:
            # something in the first list is readable
            # something in the second list is writable
            # something in the third list has an exceptional condition
            # the timeout expires
            # on windows, this only works with sockets.
            ready, _, _ = select.select([self.idle_grp_sock, self.unicast_soc], [], [], timeout)
            for sock in ready:
                received_message: Message = sock.receive()
                responses.append(received_message)
                print(f"response {received_message}")
        print(f"Collected {len(responses)} responses.")
        return responses

    def dynamic_discovery(self) -> None:
        """
        Dynamic discovery of other nodes in the idle pool.
        If no other nodes are found, declare self as INM.
        """
        self.state: Server.State = Server.State.INITIALIZING
        self.idle_grp_sock.send(MessageType.UUID_QUERY, str(self.UUID))
        print(f"Collecting UUID_QUERY...")
        responses: list[Message] = self.collect_responses(2.0)
        # filter out non-UUID_ANSWER messages
        uuid_answers: list[Message] = [msg for msg in responses if msg.message_type == MessageType.UUID_ANSWER]
        if len(uuid_answers) == 0:
            print(f"No other idle nodes alive. Declaring self = " + str(self) + " as INM.")
            self.state = Server.State.INM
        else:
            print(f"Found {len(uuid_answers)} other nodes. Joining pool of idle node(s).")
            self.state = Server.State.IDLE
            inm_response: list[Message] = [msg for msg in responses if msg.message_type == MessageType.INM_ANSWER]
            if len(inm_response) != 1:
                print(f"ERROR: recieved {len(inm_response)} inm responses instead of only 1!")
                return
            self.inm = (inm_response[0].src_ip, int(inm_response[0].src_port))
            print(f"updated {self.inm=}")
            # sort UUID addresses and find neighbor
            # join pool of idle nodes
        print("dynamic_discovery finished")

    def message_parser(self) -> None:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        raw_data, addr = self.idle_grp_sock.recvfrom(1024)   # listen for multicast messages to idle nodes
        print(f"\nparsing message {raw_data}")
        data: list[str] = raw_data.decode("utf-8").split(" ")
        if data[0] == MessageType.UUID_QUERY.value:
            print("sending UUID_ANSWER")
            self.unicast_soc.send(MessageType.UUID_ANSWER, str(self.UUID), data[2], 
            int(data[3]))
            if self.state == Server.State.INM:
                print("sending INM_ANSWER")
                self.unicast_soc.send(MessageType.INM_ANSWER, str(self.UUID), data[2], int(data[3]))
        elif data[0] == MessageType.TEST.value:
            print(f"classified as test message.")
        else:
            print("classified as unknown message.")



# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5384)


