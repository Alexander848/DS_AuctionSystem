

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
        
        #self.neighbor = None
        #self.inm = None

        self.main()

    def main(self) -> None:
        self.dynamic_discovery()
        while True:
            self.message_parser()

    def __str__(self) -> str:
        return f"Server: {self.UUID=} {self.state=}"

    def collect_responses(self, timeout: float=3.0) -> list[str]:
        """
        Collects responses from a both the multicast and the 
        unicast socket for a given amount of time.

        Example:
        responses : list[str] = self.collect_responses(1.0)
        """
        start_time: float = time.time()
        responses: list[str] = []

        while time.time() - start_time < timeout:
            # select will block until one of the following conditions are met:
            # something in the first list is readable
            # something in the second list is writable
            # something in the third list has an exceptional condition
            # the timeout expires
            # on windows, this only works with sockets.
            ready, _, _ = select.select([self.idle_grp_sock, self.unicast_soc], [], [], timeout)
            for sock in ready:
                data, addr = sock.recvfrom(1024)
                response: str = data.decode('utf-8')
                responses.append(response)
                print(f"response {response}")
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
        responses: list[str] = self.collect_responses(2.0)
        # "parse" raw responses into list
        responses: list[list[str]] = [response.split(" ") for response in responses]
        # filter out non-UUID_ANSWER messages
        responses = [response for response in responses if response[0] == MessageType.UUID_ANSWER.value]
        if len(responses) == 0:
            print(f"No other idle nodes alive. Declaring self = " + str(self) + " as INM.")
            self.state = Server.State.INM
        else:
            print(f"Found {len(responses)} other nodes. Joining pool of idle nodes.")
            self.state = Server.State.IDLE
            # save INM address
            # sort UUID addresses and find neighbor
            # join pool of idle nodes
        print("dynamic_discovery finished")

    def message_parser(self) -> None:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        data, addr = self.idle_grp_sock.recvfrom(1024)   # listen for multicast messages to idle nodes
        print(f"\nparsing message {data}")
        data: list[str] = data.decode("utf-8").split(" ")
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


