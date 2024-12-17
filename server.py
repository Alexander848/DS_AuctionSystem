

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


class Server:
    class State(Enum):
        UNINITIALIZED = 0
        IDLE = 1
        INM = 2
        AAN = 3
        PAN = 4

    def __init__(self) -> None:
        self.UUID : uuid.UUID = uuid.uuid4()     # generates a new UUID every time
        self.state : Server.State = Server.State.UNINITIALIZED
        #defaults to 127.0.0.1 for me. workaround: hardcode IP
        self.MY_IP = socket.gethostbyname(socket.gethostname())
        self.broadcast_socket = middleware.setup_broadcast_socket()
        #self.neighbor = None
        #self.inm = None

    def __str__(self) -> str:
        return f"Server {self.UUID=} {self.state=}"
    
    def dynamic_discovery(self) -> None:
        middleware.broadcast(self.broadcast_socket, f"broadcast from {self.MY_IP}", self.MY_IP)
        # listen for responses
        # mark inm
        # continue with join()

    def join(self) -> None:
        ...

    def lcr(self) -> None:
        ...


# used for dummy testing
if __name__ == "__main__":
    myserver = Server()
    print(myserver)
    myserver.dynamic_discovery()


