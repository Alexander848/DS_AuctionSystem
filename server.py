

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


import middleware
import uuid
from enum import Enum
import socket
import time
import select


class Server:
    class State(Enum):
        UNINITIALIZED = 0
        INITIALIZING = 1
        IDLE = 2
        INM = 3
        AAN = 4
        PAN = 5

    def __init__(self, port=5384) -> None:
        self.UUID: uuid.UUID = uuid.uuid4()     # generates a new UUID every time
        self.state: Server.State = Server.State.UNINITIALIZED
        self.broadcast_sock: socket.socket = middleware.setup_broadcast_socket()
        self.idle_grp_sock: socket.socket = middleware.setup_idle_grp_socket()
        self.port = port        # we need to make sure the port is unique for each IP address. TODO: how?
        self.unicast_soc: middleware.UnicastSocket = middleware.UnicastSocket(self.port)
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
        Collects responses from a socket for a given amount of time.

        Example:
        responses : list[str] = self.collect_responses(self.idle_grp_sock, 1.0)
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
        Message consists of 4 parts separated by spaces: UUID_QUERY keyword, own UUID, ip address and port (to know where to send unicasts answers to).
        """
        self.state: Server.State = Server.State.INITIALIZING
        message: str = middleware.Messages.UUID_QUERY.value + " " \
                        + str(self.UUID) + " " \
                        + str(middleware.get_my_ip()) + " " \
                        + str(self.port)
        middleware.multicast(self.idle_grp_sock, message)
        print(f"Collecting UUID_QUERY...")
        responses: list[str] = self.collect_responses(2.0)
        print(f"total {responses=}")
        # "parse" raw responses into list
        responses: list[list[str]] = [response.split(" ") for response in responses]
        # filter out non-UUID_ANSWER messages
        responses = [response for response in responses if response[0] == middleware.Messages.UUID_ANSWER.value]
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
        print(f"parsing message {data}")
        data: list[str] = data.decode("utf-8").split(" ")
        if data[0] == middleware.Messages.UUID_QUERY.value:
            print("sending UUID_ANSWER")
            self.unicast_soc.send(middleware.Messages.UUID_ANSWER, str(self.UUID), data[2], int(data[3]))
            if self.state == Server.State.INM:
                print("sending INM_ANSWER")
                self.unicast_soc.send(middleware.Messages.INM_ANSWER, str(self.UUID), data[2], int(data[3]))
        else:
            print("Received unknown message.")



# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5385)


