# uid management
# cli
# query available items
# start auction
# join auction
# bid on item

# server.py

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

from typing import Callable
import uuid
import time
import select
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
        # INITIALIZING = 1
        IDLE = 2
        INM = 3

    class Node:
        """
        This class represents server nodes in the idle group.
        It is used to manage the group view.
        """

        def __init__(self, _ip, _port, _uuid):
            print("[server.py] [Server.Node.__init__]")
            self.ip: str = _ip
            self.port: int = _port
            self.uuid: uuid.UUID = _uuid

        def __str__(self) -> str:
            print(f"  [server.py] [Server.Node.__str__] ({self.ip} {self.port} {self.uuid})")
            return f"({self.ip} {self.port} {self.uuid})"

        def __repr__(self) -> str:
            print(f"  [server.py] [Server.Node.__repr__] ({self.ip} {self.port} {self.uuid})")
            return str(self)

    def __init__(self, port=5384, set_uuid: int = -1) -> None:
        print("[server.py] [Server.__init__]")
        # we need to make sure the port is unique for each IP address. TODO: how?
        self.port: int = port
        self.ip: str = get_my_ip()
        # sets custom uuid, else generates a new UUID every time
        self.uuid: uuid.UUID = uuid.uuid4() if set_uuid == -1 else uuid.UUID(int=port)
        self.state: Server.State = Server.State.UNINITIALIZED

        self.idle_grp_sock: MulticastSocket = MulticastSocket(self.port)
        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)

        # group view consists of list of nodes. keeps track of ip, port and uuid.
        # TODO need to get rid off dead nodes over time
        self.groupview: set[Server.Node] = set([Server.Node(self.ip, self.port, self.uuid)])
        self.inm: Server.Node = Server.Node("", -1, -1)

        self.inm_thread: Thread = Thread()  # this thread is used as a timeout for election acks
        self.received_ack: bool = False  # this bool is used to communicate with the thread

        self.main()

    def main(self) -> None:
        """
        The top-level program for the state machine to execute after 
        initialization. Used to call methods which implement concrete 
        functionalities.
        """
        print(f"  [server.py] [Server.main] starting server as {self=}")
        self.dynamic_discovery()
        # causes election to start in message_parser
        self.unicast_soc.send(MessageType.ELECTION_START, str(self.uuid), self.ip, self.port)
        self.state = Server.State.IDLE
        # main loop
        while True:
            self.message_parser()

    def __str__(self) -> str:
        """
        Used to get a pretty and human readable output on str(self) 
        for debugging/logging purposes. The default behaviour prints 
        the memory address of the object.
        example: print(str(self))
        """
        print(f"  [server.py] [Server.__str__] Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}")
        return f"Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}"

    def __repr__(self) -> str:
        """
        Similar to __str__ it pretty-fies the string output. It 
        is used for concatenation with strings such that we can
        get rid of the explicit str() type conversion.
        example: print(self)
        """
        print(f"  [server.py] [Server.__repr__] Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}")
        return str(self)

    def collect_responses(self, timeout: float = 1.0) -> list[Message]:
        """
        Collects responses from a both the multicast and the 
        unicast socket for a given amount of time. Note that 
        this method is blocking.

        Example:
        responses : list[str] = self.collect_responses(1.0)
        """
        print(f"  [server.py] [Server.collect_responses]")
        start_time: float = time.time()
        responses: list[Message] = []

        while time.time() - start_time < timeout:
            # The select syscall will block until one of the following conditions are met:
            # something in the first list is readable
            # something in the second list is writable
            # something in the third list has an exceptional condition
            # the timeout expires
            # on windows, this only works with sockets.
            ready, _, _ = select.select([self.idle_grp_sock, self.unicast_soc],
                                        [],
                                        [],
                                        start_time - time.time() + timeout)
            # ready, _, _ = select.select([self.unicast_soc], [], [], timeout)
            for sock in ready:
                received_message: Message = sock.receive()
                responses.append(received_message)
                print(f"  [server.py] [Server.collect_responses] response {received_message}")
        print(f"  [server.py] [Server.collect_responses] Collected {len(responses)} responses.")
        return responses

    def dynamic_discovery(self) -> None:
        """
        Dynamic discovery of other nodes in the idle pool.
        Uses the responses to update the groupview with new
        Server.Node entries.
        """
        print(f"  [server.py] [Server.dynamic_discovery]")
        self.idle_grp_sock.send(MessageType.UUID_QUERY, str(self.uuid))
        print(f"  [server.py] [Server.dynamic_discovery] Collecting UUID_QUERY...")
        responses: list[Message] = self.collect_responses()
        # filter out non-UUID_ANSWER messages
        uuid_answers: list[Message] = [msg for msg in responses if msg.message_type == MessageType.UUID_ANSWER]
        for answer in uuid_answers:
            new_node: Server.Node = Server.Node(answer.src_ip, answer.src_port, uuid.UUID(answer.content))
            self.groupview.add(new_node)
        print(f"  [server.py] [Server.dynamic_discovery] dyn discovery finished. total nodes is {len(self.groupview)=}")

    def start_election(self) -> None:
        """
        This method sends ELECTION_START messages 
        to all nodes with a higher UUID than self.uuid
        """
        print(f"  [server.py] [Server.start_election]")
        higher_id_nodes: list[Server.Node] = [node for node in self.groupview if node.uuid > self.uuid]
        print(f"  [server.py] [Server.start_election] {len(higher_id_nodes)=}")
        for node in higher_id_nodes:
            self.unicast_soc.send(MessageType.ELECTION_START, str(self.uuid), node.ip, node.port)
        print(f"  [server.py] [Server.start_election] started election")

    def declare_inm(self, received_ack: Callable[[], bool], timeout: float = 1.0) -> None:
        """
        Used by the inm_thread to wait for the specified amount of 
        time and then check if ELECTION_ACKs have been received. If 
        not, multicast DECLARE_INM to idle group.
        """
        print(f"  [server.py] [Server.declare_inm]")
        time.sleep(timeout)
        if received_ack():
            print(f"  [server.py] [Server.declare_inm] received ack")
            return
        print(f"  [server.py] [Server.declare_inm] declaring itself inm")
        self.state = Server.State.INM
        self.idle_grp_sock.send(MessageType.DECLARE_INM, str(self.uuid))

    def message_parser(self) -> None:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        # wait for a message on either the idle group socket or the unicast socket
        ready, _, _ = select.select([self.idle_grp_sock, self.unicast_soc], [], [])
        msg: Message = ready[0].receive()
        print(f"    [server.py] [Server.message_parser] {msg}")
        if msg.message_type == MessageType.UUID_QUERY:
            print(f"    [server.py] [Server.message_parser] UUID_QUERY")
            self.groupview.add(Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content)))
            self.unicast_soc.send(MessageType.UUID_ANSWER, str(self.uuid), msg.src_ip, msg.src_port)
        elif msg.message_type == MessageType.ELECTION_START:
            print(f"    [server.py] [Server.message_parser] ELECTION_START")
            if msg.content != str(self.uuid):
                self.unicast_soc.send(MessageType.ELECTION_ACK, "", msg.src_ip, msg.src_port)
            self.start_election()
            print(f"    [server.py] [Server.message_parser] starting inm thread")
            self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
            self.inm_thread.start()
        elif msg.message_type == MessageType.ELECTION_ACK:
            print(f"    [server.py] [Server.message_parser] ELECTION_ACK")
            print(f"    [server.py] [Server.message_parser] cancelling inm thread")
            self.received_ack = True
            self.inm_thread.join()
            self.received_ack = False
        elif msg.message_type == MessageType.DECLARE_INM:
            print(f"    [server.py] [Server.message_parser] DECLARE_INM")
            self.inm = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
            print(f"    [server.py] [Server.message_parser] DECLARE_INM {self.inm}")
        elif msg.message_type == MessageType.TEST:
            print(f"    [server.py] [Server.message_parser] TEST_MESSAGE")
        else:
            print("     [server.py] [Server.message_parser] ERROR: Unknown message")


# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5384)