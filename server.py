

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
        self.port = port
        self.unicast_soc: socket.socket = middleware.setup_unicast_socket(self.port)
        #self.MY_IP = middleware.get_my_ip()
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
        """
        self.state : Server.State = Server.State.INITIALIZING
        middleware.multicast(self.idle_grp_sock, middleware.Messages.DISCOVERY.value)
        responses : list[str] = self.collect_responses(self.idle_grp_sock, 1.0)
        print(responses)
        if len(responses) <= 1:
            print("No other nodes alive. Declaring self as INM.")
            self.state = Server.State.INM
        else:
            print("Found other nodes. Joining pool of idle nodes.")
            self.state = Server.State.IDLE

            # save INM address
            # sort UUID addresses and find neighbor
            # join pool of idle nodes
        #self.message_parser()
        


    def join(self) -> None:
        ...



    def lcr(self) -> None:
        ...



    def message_parser(self) -> None:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        data, addr = self.idle_grp_sock.recvfrom(1024)
        data = data.decode("utf-8")
        print(f"Received {data} from {addr}")
        if data == middleware.Messages.DISCOVERY.value:
            middleware.multicast(self.idle_grp_sock, middleware.Messages.INM.value)
        else:
            print("Received unknown message.")


# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5385)


