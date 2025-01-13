

# every server:
# uid management
# dynamic discovery
# join pool of idle nodes
# LCR -> bully algorithm

# for INM:
# start auction
# middleware detects crashes -> repair ring, re-election

# active auctioneer node aan:
# manage auction
# replicate to passive auctioneer nodes pan
# finalize auction

# passive auctioneer node pan:
# detect aan failures, re-elect

from typing import Callable, NoReturn
import uuid
import time
from enum import Enum
from threading import Thread

from middleware import Message
from middleware import MessageType
from middleware import get_my_ip
from middleware.multicast import MulticastSocket
from middleware.unicast import UnicastSocket


class Server:
    """
    The server class to manage server nodes. Every node is 
    modeled after a state machine. 
    """
    
    class State(Enum):
        """
        The possible states which any given node can be in.
        """
        UNINITIALIZED = 0
        #INITIALIZING = 1
        IDLE = 2
        INM = 3


    class Node:
        """
        This class represents server nodes in the idle group.
        It is used to manage the group view.
        """
        def __init__(self, _ip: str, _port: int, _uuid: uuid.UUID) -> None:
            self.ip: str = _ip
            self.port: int = _port
            self.uuid: uuid.UUID = _uuid

        def __str__(self) -> str:
            return f"({self.ip} {self.port} {self.uuid})"
        
        def __repr__(self) -> str:
            return str(self)


    def __init__(self, port: int=5384, set_uuid: int=-1) -> None:
        """
        This is the constructer of the Server class and is 
        the first method which executes. It declares the
        member variables of a node and initializes them.
        Also note the call to the main() method at the end
        to transfer the program flow.
        """
        # we need to make sure the port is unique for each IP address. TODO: how?
        self.port: int = port
        self.ip: str= get_my_ip()
        # sets custom uuid, else generates a new UUID every time
        self.uuid: uuid.UUID = uuid.uuid4() if set_uuid==-1 else uuid.UUID(int=port)    
        self.state: Server.State = Server.State.UNINITIALIZED
        
        self.idle_grp_sock: MulticastSocket = MulticastSocket(self.port)
        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)
        
        # group view consists of list of nodes. keeps track of ip, port and uuid.
        # TODO need to get rid off dead nodes over time
        self.groupview: set[Server.Node] = set([Server.Node(self.ip, self.port, self.uuid)])
        self.inm: Server.Node = Server.Node("", -1, uuid.UUID(int=0))

        self.inm_thread: Thread = Thread()      # this thread is used as a timeout for election acks 
        self.received_ack: bool = False         # this bool is used to communicate with the thread

        self.main()

    def main(self) -> None:
        """
        The top-level program for the state machine to execute after 
        initialization. Used to call methods which implement concrete 
        functionalities.
        """
        print(f"starting server as {self=}")
        self.dynamic_discovery()
        # causes election to start in message_parser
        self.unicast_soc.send(MessageType.ELECTION_START, str(self.uuid), self.ip, self.port)
        self.state = Server.State.IDLE
        # main loop
        unicast_parser: Thread = Thread(target=self.message_parser, args=(self.unicast_soc,))
        multicast_parser: Thread = Thread(target=self.message_parser, args=(self.idle_grp_sock,))
        unicast_parser.start()
        multicast_parser.start()

    def __str__(self) -> str:
        """
        Used to get a pretty and human readable output on str(self) 
        for debugging/logging purposes. The default behaviour prints 
        the memory address of the object.
        example: print(str(self))
        """
        return f"Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}"
    
    def __repr__(self) -> str:
        """
        Similar to __str__ it pretty-fies the string output. It 
        is used for concatenation with strings such that we can
        get rid of the explicit str() type conversion.
        example: print(self)
        """
        return str(self)


    def dynamic_discovery(self) -> None:
        """
        Dynamic discovery of other nodes in the idle pool.
        Uses the responses to update the groupview with new
        Server.Node entries.
        """
        self.idle_grp_sock.send(MessageType.UUID_QUERY, str(self.uuid))
        print(f"Collecting UUID_QUERY...")
        time.sleep(1.0) # timeout of 1 second
        responses: list[Message] = list(self.unicast_soc.delivered.queue)
        self.unicast_soc.delivered.queue.clear()
        # filter out non-UUID_ANSWER messages
        uuid_answers: list[Message] = [msg for msg in responses if msg.message_type == MessageType.UUID_ANSWER]
        for answer in uuid_answers:
            new_node: Server.Node = Server.Node(answer.src_ip, answer.src_port, uuid.UUID(answer.content))
            self.groupview.add(new_node)
        print(f"dyn discovery finished. total nodes is {len(self.groupview)=}")

    def start_election(self) -> None:
        """
        This method sends ELECTION_START messages 
        to all nodes with a higher UUID than self.uuid
        """
        higher_id_nodes: list[Server.Node] = [node for node in self.groupview if node.uuid > self.uuid ]
        print(f"{len(higher_id_nodes)=}")
        for node in higher_id_nodes:
            self.unicast_soc.send(MessageType.ELECTION_START, str(self.uuid), node.ip, node.port)
        print(f"started election")

    def declare_inm(self, received_ack: Callable[[], bool], timeout: float=1.0) -> None:
        """
        Used by the inm_thread to wait for the specified amount of 
        time and then check if ELECTION_ACKs have been received. If 
        not, multicast DECLARE_INM to idle group.
        """
        time.sleep(timeout)
        if received_ack():
            return
        print(f"declaring itself inm")
        self.state = Server.State.INM
        self.idle_grp_sock.send(MessageType.DECLARE_INM, str(self.uuid))

    def message_parser(self, listen_sock: UnicastSocket | MulticastSocket) -> NoReturn:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        # wait for a message to be processed
        while True:
            msg: Message = listen_sock.delivered.get()
            print(f"parsing {msg}")
            if msg.message_type == MessageType.UUID_QUERY:
                self.groupview.add(Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content)))
                self.unicast_soc.send(MessageType.UUID_ANSWER, str(self.uuid), msg.src_ip, msg.src_port)
            elif msg.message_type == MessageType.ELECTION_START:
                print("Got Election Start: {}".format(msg))
                if msg.content != str(self.uuid):
                    self.unicast_soc.send(MessageType.ELECTION_ACK, "", msg.src_ip, msg.src_port)
                self.start_election()
                print(f"starting inm thread")
                self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
                self.inm_thread.start()
            elif msg.message_type == MessageType.ELECTION_ACK:
                print(f"cancelling inm thread")
                self.received_ack = True
                self.inm_thread.join()
                self.received_ack = False
            elif msg.message_type == MessageType.DECLARE_INM:
                self.inm = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
                print(f"new {self.inm=}")
            elif msg.message_type == MessageType.TEST:
                print(f"TEST_MESSAGE")
            else:
                print(f"ERROR: Unknown message: {msg}")



# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5384)


