
from queue import Empty#, Queue
from typing import Callable, NoReturn
import uuid
import time
from enum import Enum
from threading import Thread
import threading
import sys

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
        AAN = 4
        PAN = 5


    class Node:
        """
        This class represents server nodes in the idle group.
        It is used to manage the group view.
        """

        def __init__(self, _ip: str, _port: int, _uuid: uuid.UUID) -> None:
            print("[server.py] [Server.Node.__init__]")
            self.ip: str = _ip
            self.port: int = _port
            self.uuid: uuid.UUID = _uuid
            self.last_heartbeat = time.time()

        def __str__(self) -> str:
            #print(f"  [server.py] [Server.Node.__str__] ({self.ip} {self.port} {self.uuid})")
            return f"({self.ip} {self.port} {self.uuid})"

        def __repr__(self) -> str:
            #print(f"  [server.py] [Server.Node.__repr__] ({self.ip} {self.port} {self.uuid})")
            return str(self)

    def __init__(self, port: int=5384, set_uuid: int=-1) -> None:
        print("[server.py] [Server.__init__]")
        # Simple item list (list of dictionaries)
        self.item_data: list[dict[str, int | str]] = [
            {"itemID": 1, "itemname": "Master Sword", "price": 1000},
            {"itemID": 2, "itemname": "Hylian Shield", "price": 500},
            {"itemID": 3, "itemname": "Hookshot", "price": 300},
            {"itemID": 4, "itemname": "Boomerang", "price": 200},
        ]
        # we need to make sure the port is unique for each IP address. TODO: how?
        self.port: int = port
        self.ip: str = get_my_ip()
        # sets custom uuid, else generates a new UUID every time
        self.uuid: uuid.UUID = uuid.uuid4() if set_uuid == -1 else uuid.UUID(int=set_uuid)
        self.state: Server.State = Server.State.UNINITIALIZED

        self.idle_grp_sock: MulticastSocket = MulticastSocket(self.port)
        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)

        # Once set to true, stops all threads
        self.stop_execution : bool = False

        # group view consists of list of nodes. keeps track of ip, port and uuid.
        self.groupview: set[Server.Node] = set()
        self.inm: Server.Node | None = None
        self.pan_node: Server.Node | None = None # Keep track of the assigned PAN

        self.inm_thread: Thread = Thread()  # this thread is used as a timeout for election acks
        self.received_ack: bool = False  # this bool is used to communicate with the thread
        self.state_port: int = 9999  # port for state queries. cannot be used by other server nodes

        self.info_thread: Thread = Thread(target=self.periodic_info_print)
        self.info_thread.daemon = True  # Allow the main thread to exit even if this thread is running
        self.info_thread.start()

        self._heartbeat_thread = None
        self._heartbeat_stop_event = threading.Event()
        self.election_in_progress: bool = False

        # Heartbeat constants
        self.HEARTBEAT_INTERVAL = 10  # Example: 5 seconds
        self.HEARTBEAT_TIMEOUT = 2 * self.HEARTBEAT_INTERVAL
        self.heartbeat_counter = 0
        self.GROUPVIEW_UPDATE_HEARTBEAT_INTERVAL = 2  # Send update every 2nd heartbeat

        #self.state_response_queue: Queue[Message] = Queue()

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

        # Start the centralized heartbeat thread once after initialization
        self.start_heartbeat_thread()

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
        #print(f"  [server.py] [Server.__str__] Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}")
        return f"Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}"

    def __repr__(self) -> str:
        """
        Similar to __str__ it pretty-fies the string output. It 
        is used for concatenation with strings such that we can
        get rid of the explicit str() type conversion.
        example: print(self)
        """
        #print(f"  [server.py] [Server.__repr__] Server: {self.uuid=} {self.state.value=} {self.ip} {self.port}")
        return str(self)

    def print_info(self) -> None:
        """Prints the server's information to the console."""
        print(f"\n                    ===== Server Info =====")
        print(f"                    UUID: {self.uuid}")
        print(f"                    State: {self.state.name}")
        print(f"                    IP: {self.ip}")
        print(f"                    Port: {self.port}")
        print(f"                    INM: {self.inm}")
        # Print only the ports of nodes in the groupview
        groupview_ports = [node.port for node in self.groupview]
        print(f"                    Groupview Ports: {groupview_ports}")
        # Display running threads
        #print(f"Election in progress: {self.election_in_progress}")
        print("                    Running Threads:")
        for thread in threading.enumerate():
            if thread != threading.current_thread():  # Exclude the main thread if needed
                print(f"                      - {thread.name} (daemon: {thread.daemon})")
        if self.state == Server.State.AAN:
            if self.pan_node is not None:
                print(f"                    PAN: {self.pan_node.uuid} ({self.pan_node.ip}:{self.pan_node.port})")
            if hasattr(self, 'item_id'):
                print(f"                        Auction Item: {self.item_id}")
            if hasattr(self, 'highest_bid'):
                print(f"                        Highest Bid: {self.highest_bid}")
            if hasattr(self, 'highest_bidder'):
                print(f"                        Highest Bidder: {self.highest_bidder}")
            if hasattr(self, 'client_address'):
                print(f"                        Client: {self.client_address}")
            if hasattr(self, 'clients'):
                print(f"                        Clients: {self.clients}")
            if hasattr(self, 'auction_timer'):
                print(f"                        Time left: {int(self.auction_end_time - time.time())}")
        elif self.state == Server.State.PAN:
            if self.aan_node is not None:
                print(f"                    AAN: {self.aan_node.uuid} ({self.aan_node.ip}:{self.aan_node.port})")
            if hasattr(self, 'item_id'):
                print(f"                        Auction Item: {self.item_id}")
            if hasattr(self, 'highest_bid'):
                print(f"                        Highest Bid: {self.highest_bid}")
            if hasattr(self, 'highest_bidder'):
                print(f"                        Highest Bidder: {self.highest_bidder}")
            if hasattr(self, 'client_address'):
                print(f"                        Client: {self.client_address}")
            if hasattr(self, 'clients'):
                print(f"                        Clients: {self.clients}")
            if hasattr(self, 'auction_timer'):
                print(f"                        Time left: {int(self.auction_end_time - time.time())}")
        print(f"                    =======================\n")

    def periodic_info_print(self) -> None:
        """Periodically prints the server's information."""
        while True:
            self.print_info()
            time.sleep(5)
            # stops heartbeat thread and sends message to stop uni/multicast receive/deliver threads
            # and message parser thread
            if self.stop_execution:
                self.stop_heartbeat_thread()
                self.unicast_soc.send(MessageType.STOP_EXECUTION, "test", self.ip, self.port)
                self.idle_grp_sock.send(MessageType.STOP_EXECUTION, str(self.ip) + "," + str(self.port))   # no ack because this is for testing purposes only
                return


    def get_available_items_from_api(self) -> list[dict[str, int | str]]:
        # Here, we just return the simple item_data list
        return self.item_data

    def dynamic_discovery(self) -> None:
        """
        Dynamic discovery of other nodes in the idle pool.
        Uses the responses to update the groupview with new
        Server.Node entries.
        """
        print(f"  [server.py] [Server.dynamic_discovery]")
        self.idle_grp_sock.send(MessageType.UUID_QUERY, str(self.uuid))     # dynamic discovery, acks are implied by UUID_ANSWER
        print(f"  [server.py] [Server.dynamic_discovery] Collecting UUID_QUERY...")
        time.sleep(1.0) # collect responses for 1 second
        responses: list[Message] = list(self.unicast_soc.delivered.queue)
        self.unicast_soc.delivered.queue.clear()
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
        # Skip election if currently active in an auction
        if self.state in [Server.State.AAN, Server.State.PAN]:
            print("Currently in an active auction role; skipping election.")
            return
        self.election_in_progress = True
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

        # handle reliable multicast through acks and retransmissions
        # -> doesnt need deduplication because the messages are idempotent
        self.waiting_on_inm_ack: list[uuid.UUID] = [node.uuid for node in self.groupview]
        inm_ack_thread: Thread = Thread(target=self.inm_ack, name="INMAckThread")
        inm_ack_thread.start()
        
        self.idle_grp_sock.send(MessageType.DECLARE_INM, str(self.uuid))    # ack handled right above

        # Election is finished (this node is INM)
        self.election_in_progress = False

    def inm_ack(self) -> None:
        time.sleep(1)
        unacked_nodes: list[Server.Node] = [node for node in self.groupview if node.uuid in self.waiting_on_inm_ack]
        for node in unacked_nodes:
            print(f"###  [server.py] [Server.inm_ack] UNACKED Sending DECLARE_INM to unacknowledged node {node}")
            self.unicast_soc.send(MessageType.DECLARE_INM, str(self.uuid), node.ip, node.port)


    def message_parser(self, listen_sock: UnicastSocket | MulticastSocket) -> NoReturn | None:
        """
        Continuously listens for messages from the network.
        Messages are then parsed and forwarded to the correct handler.
        """
        while True:
            # wait for a message to be processed
            msg: Message = listen_sock.delivered.get()
            #print(f"parsing {msg}")

            # receiving a STOP_EXECUTION message stops messageParser Thread and uni/multicast deliver/receive threads
            if self.stop_execution is True:
                if msg.message_type is not MessageType.STOP_EXECUTION:
                    continue
                else:
                    return

            if msg.message_type == MessageType.UUID_QUERY:
                print(f"    [server.py] [Server.message_parser] Received UUID_QUERY from {msg.src_ip}:{msg.src_port}")

                # Add the new node to the groupview
                self.groupview.add(Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content)))
                # Send the UUID back to the requester
                self.unicast_soc.send(MessageType.UUID_ANSWER, str(self.uuid), msg.src_ip, msg.src_port)

            elif msg.message_type == MessageType.UUID_ANSWER:
                print(f"    [server.py] [Server.message_parser] Received UUID_ANSWER from {msg.src_ip}:{msg.src_port}")

            elif msg.message_type == MessageType.ELECTION_START:
                print(f"    [server.py] [Server.message_parser] Received ELECTION_START from {msg.src_ip}:{msg.src_port}")

                # Skip election if currently active in an auction
                if self.state in [Server.State.AAN, Server.State.PAN]:
                    print("    [server.py] [Server.message_parser] Skipping ELECTION_START, currently in active auction role.")
                    continue
                # If the received UUID is not my own, acknowledge the election
                if msg.content != str(self.uuid):
                    self.unicast_soc.send(MessageType.ELECTION_ACK, "", msg.src_ip, msg.src_port)
                # Start the election process
                self.start_election()
                print(f"    [server.py] [Server.message_parser] Starting INM declaration thread")
                # Create and start the INM declaration thread
                self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
                self.inm_thread.start()

            elif msg.message_type == MessageType.ELECTION_ACK:
                print(f"    [server.py] [Server.message_parser] Received ELECTION_ACK from {msg.src_ip}:{msg.src_port}")

                # Skip election if currently active in an auction
                if self.state in [Server.State.AAN, Server.State.PAN]:
                    print("    [server.py] [Server.message_parser] Skipping ELECTION_ACK, currently in active auction role.")
                    continue
                print(f"    [server.py] [Server.message_parser] Cancelling INM declaration thread")
                # Set the flag to indicate that an ACK has been received
                self.received_ack = True
                # Wait for the INM thread to finish
                self.inm_thread.join()
                # Reset the flag
                self.received_ack = False

            elif msg.message_type == MessageType.DECLARE_INM:
                print(f"    [server.py] [Server.message_parser] Received DECLARE_INM from {msg.src_ip}:{msg.src_port}")

                # acknowledge the declare_inm
                self.unicast_soc.send(MessageType.DECLARE_INM_ACK, str(self.uuid), msg.src_ip, msg.src_port)

                # Skip election if currently active in an auction
                if self.state in [Server.State.AAN, Server.State.PAN]:
                    # still update INM TODO: test scenario: auction active, INM fails, INM reassigned, PAN/AAN fails -> need current INM_address for PAN/AAN request
                    self.inm = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
                    print("    [server.py] [Server.message_parser] Skipping DECLARE_INM, currently in active auction role.")
                    continue
                # If the message is not from this server, set state to IDLE and update INM
                if msg.src_port != self.port:
                    self.state = Server.State.IDLE
                    self.election_in_progress = False  # Election is finished (another node is INM)
                    print(f"    [server.py] [Server.message_parser] DECLARE_INM: Server {self.port} back to IDLE")
                # Update the INM node information
                self.inm = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
                print(f"    [server.py] [Server.message_parser] New INM is set to {self.inm}")

            elif msg.message_type == MessageType.DECLARE_INM_ACK:
                print(f"    [server.py] [Server.message_parser] Received DECLARE_INM_ACK from {msg.src_ip}:{msg.src_port}")
                if uuid.UUID(msg.content) in self.waiting_on_inm_ack:
                    self.waiting_on_inm_ack.remove(uuid.UUID(msg.content))

            elif msg.message_type == MessageType.TEST:
                print(f"    [server.py] [Server.message_parser] Received TEST from {msg.src_ip}:{msg.src_port}")

            elif msg.message_type == MessageType.CONNECT_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received CONNECT_REQUEST from {msg.src_ip}:{msg.src_port}")

                # If this server is the INM, send its IP and port to the requester
                if self.state == Server.State.INM:
                    self.unicast_soc.send(
                        MessageType.CONNECT_RESPONSE,
                        f"{self.ip}:{self.port}",  # Send INM's IP and port
                        msg.src_ip,
                        msg.src_port,
                    )

            elif msg.message_type == MessageType.STATE_QUERY:
                print(f"    [server.py] [Server.message_parser] Received STATE_QUERY from {msg.src_ip}:{msg.src_port}")

                # Respond to the state query with the requester's UUID and this server's state
                response_content = f"{msg.content},{self.state.name}"
                self.unicast_soc.send(MessageType.STATE_RESPONSE, response_content, msg.src_ip, msg.src_port)

            #elif msg.message_type == MessageType.STATE_RESPONSE:
            #    print(f"    [server.py] [Server.message_parser] Received STATE_RESPONSE from {msg.src_ip}:{msg.src_port}")
            #    self.state_response_queue.put(msg)

            elif msg.message_type == MessageType.LIST_ITEMS_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received LIST_ITEMS_REQUEST from {msg.src_ip}:{msg.src_port}")

                # If this server is the INM, query the external API for available items
                if self.state == Server.State.INM:
                    available_items = self.get_available_items_from_api()  # TODO Implement this
                    # Format the item list as a string
                    items_str = ""
                    for item in available_items:
                        items_str += f"{item['itemID']},{item['itemname']},{item['price']};"
                    # Remove the trailing semicolon and replace spaces for message parsing
                    items_str = items_str.rstrip(";").replace(" ", "")
                    # Send the item list to the client
                    self.unicast_soc.send(
                        MessageType.LIST_ITEMS_RESPONSE,
                        items_str,
                        msg.src_ip,
                        msg.src_port,
                    )

            elif msg.message_type == MessageType.START_AUCTION_REQUEST:
                print(
                    f"    [server.py] [Server.message_parser] Received START_AUCTION_REQUEST for item {msg.content} from {msg.src_ip}:{msg.src_port}")

                # If this server is the INM, start an auction for the requested item
                if self.state == Server.State.INM:
                    self.start_auction(int(msg.content), msg.src_ip, msg.src_port)

            elif msg.message_type == MessageType.AUCTION_INIT:
                print(f"    [server.py] [Server.message_parser] Received AUCTION_INIT from {msg.src_ip}:{msg.src_port}")

                # If this server is IDLE, it can become an AAN and initialize an auction
                if self.state == Server.State.IDLE:  # Only idle nodes can become AANs
                    item_id, client_ip, client_port = msg.content.split(",")
                    self.initialize_auction(item_id, client_ip, int(client_port))

            elif msg.message_type == MessageType.PAN_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received PAN_REQUEST for item {msg.content} from {msg.src_ip}:{msg.src_port}")

                # If this server is the INM, it handles the request to assign a PAN
                if self.state == Server.State.INM:
                    self.request_pan(msg.content)

            elif msg.message_type == MessageType.PAN_RESPONSE:
                print(f"    [server.py] [Server.message_parser] Received PAN_RESPONSE from {msg.src_ip}:{msg.src_port}")

                # If this server is IDLE, it can become a PAN
                if self.state == Server.State.IDLE:  # Only idle nodes can become PANs
                    self.set_as_pan(msg.content)

            elif msg.message_type == MessageType.PAN_FAILURE:
                print(f"    [server.py] [Server.message_parser] Received PAN_FAILURE from {msg.src_ip}:{msg.src_port}")

                # If this server is an AAN, it logs the PAN failure
                if self.state == Server.State.AAN:
                    print(f"    [server.py] [Server.message_parser] PAN_FAILURE: No PAN assigned for the auction.")

            elif msg.message_type == MessageType.PAN_INFO:
                print(f"    [server.py] [Server.message_parser] Received PAN_INFO from {msg.src_ip}:{msg.src_port}")

                # If this server is an AAN, it stores the PAN's information
                if self.state == Server.State.AAN:
                    pan_ip, pan_port, pan_uuid = msg.content.split(",")
                    self.pan_node = Server.Node(pan_ip, int(pan_port), uuid.UUID(pan_uuid))
                    print(f"    [server.py] [Server.message_parser] AAN received and stored PAN information: {self.pan_node}")

            elif msg.message_type == MessageType.JOIN_AUCTION_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received JOIN_AUCTION_REQUEST from {msg.src_ip}:{msg.src_port}")

                # If this server is an AAN, it handles a client's request to join an auction
                if self.state == Server.State.AAN:
                    item_id, client_uuid = msg.content.split(",")
                    # Only process if this AAN is responsible for the item_id
                    if item_id == self.item_id:
                        self.join_auction(item_id, client_uuid, msg.src_ip, msg.src_port)

            elif msg.message_type == MessageType.BID_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received BID_REQUEST from {msg.src_ip}:{msg.src_port}")

                # If this server is an AAN, it handles a client's bid request
                if self.state == Server.State.AAN:
                    item_id, bid_amount, client_uuid = msg.content.split(",")
                    bid_amount = int(bid_amount)

                    # Calculate remaining time for the auction
                    remaining_time = int(self.auction_end_time - time.time())
                    if remaining_time < 0:
                        remaining_time = 0

                    # Check if the bid is valid
                    if item_id == self.item_id and bid_amount > int(self.highest_bid):
                        self.highest_bid = bid_amount
                        self.highest_bidder = client_uuid
                        self.replicate_state()  # Replicate the updated state to the PAN
                        # Send acceptance response to the client
                        self.unicast_soc.send(MessageType.BID_RESPONSE,
                                            f"Bid-for-{item_id}-accepted-for-amount-{bid_amount}-timeleft-{remaining_time}",
                                            msg.src_ip,
                                            msg.src_port)
                        print(
                            f"    [server.py] [Server.message_parser] Accepted bid for item {item_id} from {client_uuid} for {bid_amount}")
                    else:
                        # Send rejection response to the client
                        self.unicast_soc.send(MessageType.BID_RESPONSE,
                                            f"Bid-for-{item_id}-for-{bid_amount}-rejected-because-smaller-than-highest_bid-{self.highest_bid}-timeleft-{remaining_time}",
                                            msg.src_ip, msg.src_port)
                        print(f"    [server.py] [Server.message_parser] Rejected bid for item {item_id} from {client_uuid} for {bid_amount}")

            elif msg.message_type == MessageType.REPLICATE_STATE:
                print(
                    f"    [server.py] [Server.message_parser] Received REPLICATE_STATE for item {msg.content.split(',')[0]} from {msg.src_ip}:{msg.src_port}")

                # If this server is a PAN, it updates its state based on the AAN's message
                if self.state == Server.State.PAN:
                    # Parse the message content to update state
                    parts = msg.content.split(",", 4)
                    if len(parts) == 5:
                        item_id, highest_bid, highest_bidder, client_list_str, remaining_time_str = parts
                    else:
                        # Handle cases where client_list_str might include commas
                        item_id, highest_bid, highest_bidder, rest = parts[0], parts[1], parts[2], parts[3]
                        client_list_str, remaining_time_str = rest.rsplit(",", 1)

                    self.item_id = item_id
                    self.highest_bid = int(highest_bid)
                    self.highest_bidder = highest_bidder if highest_bidder != "None" else None
                    remaining_time = int(remaining_time_str)

                    # Update the client list
                    self.clients: list[tuple[str, int, str]] = []
                    if client_list_str:  # Check if the string is not empty
                        for client_str in client_list_str.split(";"):
                            client_ip, client_port, client_uuid = client_str.split(":")
                            self.clients.append((client_ip, int(client_port), client_uuid))

                    # Set new auction_end_time and restart the timer if needed
                    if remaining_time > 0:
                        self.auction_end_time = time.time() + remaining_time
                        if hasattr(self, 'auction_timer'):
                            self.auction_timer.cancel()  # Cancel any existing timer
                        self.auction_timer = threading.Timer(remaining_time, self.finalize_auction)
                        self.auction_timer.name = "AuctionTimerThread"
                        self.auction_timer.start()

                    print(
                        f"    [server.py] [Server.message_parser] Updated PAN state: item_id={item_id}, highest_bid={self.highest_bid}, highest_bidder={self.highest_bidder}, clients={self.clients}, remaining_time={remaining_time}")

            elif msg.message_type == MessageType.REPLICATE_STATE_REQUEST:
                print(
                    f"    [server.py] [Server.message_parser] Received REPLICATE_STATE_REQUEST from {msg.src_ip}:{msg.src_port}")

                # If this server is an AAN, it replicates its state to the PAN
                if self.state == Server.State.AAN:
                    self.replicate_state()

            elif msg.message_type == MessageType.AUCTION_END:
                print(f"    [server.py] [Server.message_parser] Received AUCTION_END from {msg.src_ip}:{msg.src_port}")

                # If this server is a PAN, it returns to the IDLE state
                if self.state == Server.State.PAN:
                    self.return_to_idle()

            elif msg.message_type == MessageType.HEARTBEAT_REQUEST:
                print(f"    [server.py] [Server.message_parser] Received HEARTBEAT_REQUEST from {msg.src_ip}:{msg.src_port}")

                # Respond to the heartbeat request
                self.unicast_soc.send(MessageType.HEARTBEAT_RESPONSE, str(self.uuid), msg.src_ip, msg.src_port)
                # If this server is the INM, update the groupview and send updates if necessary
                if self.state == Server.State.INM:
                    # Check if the node is already in the groupview
                    node_exists = any(node.ip == msg.src_ip and node.port == msg.src_port for node in self.groupview)

                    if not node_exists:
                        print(
                            f"    [server.py] [Server.message_parser] Re-adding node {msg.src_ip}:{msg.src_port} to groupview")
                        new_node = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
                        self.groupview.add(new_node)
                        self.send_groupview_update()  # Send groupview update after re-adding
                    # Update the node's last heartbeat
                    for node in self.groupview:
                        if node.ip == msg.src_ip and node.port == msg.src_port:
                            node.last_heartbeat = time.time()
                            break
                # If this server is IDLE, update the INM's last heartbeat
                if self.state == Server.State.IDLE and self.inm:
                    self.inm.last_heartbeat = time.time()

                # If this server is an AAN, update the PAN's last heartbeat
                elif self.state == Server.State.AAN and self.pan_node and msg.src_ip == self.pan_node.ip and msg.src_port == self.pan_node.port:
                    self.pan_node.last_heartbeat = time.time()

                # If this server is a PAN, update the AAN's last heartbeat
                elif self.state == Server.State.PAN and self.aan_node and msg.src_ip == self.aan_node.ip and msg.src_port == self.aan_node.port:
                    self.aan_node.last_heartbeat = time.time()

            elif msg.message_type == MessageType.HEARTBEAT_RESPONSE:
                print(
                    f"    [server.py] [Server.message_parser] Received HEARTBEAT_RESPONSE from {msg.src_ip}:{msg.src_port}")

                # If this server is the INM, update the groupview and send updates if necessary
                if self.state == Server.State.INM:
                    # Check if the node is already in the groupview
                    node_exists = any(node.ip == msg.src_ip and node.port == msg.src_port for node in self.groupview)

                    if not node_exists:
                        print(
                            f"    [server.py] [Server.message_parser] Re-adding node {msg.src_ip}:{msg.src_port} to groupview")
                        new_node = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
                        self.groupview.add(new_node)
                        self.send_groupview_update()  # Send groupview update after re-adding
                    # Update the node's last heartbeat
                    for node in self.groupview:
                        if node.ip == msg.src_ip and node.port == msg.src_port:
                            node.last_heartbeat = time.time()
                            break

                # If this server is IDLE, update the INM's last heartbeat
                elif self.state == Server.State.IDLE and self.inm and self.inm.ip == msg.src_ip and self.inm.port == msg.src_port:
                    self.inm.last_heartbeat = time.time()

                # If this server is an AAN, update the PAN's last heartbeat
                elif self.state == Server.State.AAN and self.pan_node and msg.src_ip == self.pan_node.ip and msg.src_port == self.pan_node.port:
                    self.pan_node.last_heartbeat = time.time()
                # If this server is a PAN, update the AAN's last heartbeat
                elif self.state == Server.State.PAN and self.aan_node and msg.src_ip == self.aan_node.ip and msg.src_port == self.aan_node.port:
                    self.aan_node.last_heartbeat = time.time()

            elif msg.message_type == MessageType.GROUPVIEW_UPDATE:
                print(f"    [server.py] [Server.message_parser] Received GROUPVIEW_UPDATE from {msg.src_ip}:{msg.src_port}")

                # acknowledge the groupview
                self.unicast_soc.send(MessageType.GROUPVIEW_ACK, str(self.uuid), msg.src_ip, msg.src_port)

                # If this server is IDLE, update its groupview
                if self.state == Server.State.IDLE:
                    new_groupview: set[Server.Node] = set()
                    nodes_str = msg.content.split(";")
                    # Parse the new groupview information
                    for node_str in nodes_str:
                        ip, port, uuid_str = node_str.split(":")
                        new_groupview.add(Server.Node(ip, int(port), uuid.UUID(uuid_str)))
                    self.groupview = new_groupview
                    print(f"    [server.py] [Server.message_parser] Updated groupview: {self.groupview}")

            elif msg.message_type == MessageType.GROUPVIEW_ACK:
                print(f"    [server.py] [Server.message_parser] Received GROUPVIEW_ACK from {msg.src_ip}:{msg.src_port}")
                #print(f"{msg=}")
                #print(f"{self.waiting_on_groupview_ack=}")
                if uuid.UUID(msg.content) in self.waiting_on_groupview_ack:
                    self.waiting_on_groupview_ack.remove(uuid.UUID(msg.content))

            else:
                print(f"     [server.py] [Server.message_parser] ERROR: Unknown message: {msg}, {type(listen_sock)}")

    def start_auction(self, item_id: int, client_ip: str, client_port: int) -> None:
        """
        Handles the START_AUCTION_REQUEST when the server is the INM.

        This method orchestrates the process of initiating an auction by:
        1. Selecting an idle node from the groupview to act as the Auctioneer Node (AAN).
        2. Informing the selected AAN about its role and providing necessary auction data.
        3. Responding to the client with the AAN's address for further auction-related communication.

        Args:
            item_id: The ID of the item to be auctioned.
            client_ip: The IP address of the client initiating the auction request.
            client_port: The port number of the client.
        """
        print(f"  [server.py] [Server.start_auction] Received START_AUCTION_REQUEST for item '{item_id}' from {client_ip}:{client_port}")

        # only positive numbers allowed
        if item_id < 0:
            print(f"  [server.py] [Server.start_auction] Invalid item ID: {item_id}")
            self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, "ERROR:InvaliditemID", client_ip, client_port)
            return
        # item has to be in store
        if item_id not in [item['itemID'] for item in self.get_available_items_from_api()]:
            print(f"  [server.py] [Server.start_auction] Item '{item_id}' not found in available items.")
            self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, "ERROR:Itemnotavailableforstart", client_ip, client_port)
            return            

        # 1. Select an Idle Node as AAN
        aan_node = self.select_idle_node()

        if aan_node is None:
            print(f"  [server.py] [Server.start_auction] No idle nodes available.")
            self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, "ERROR:Noidlenodesavailable", client_ip, client_port)
            return
        print(f"  [server.py] [Server.start_auction] Selected {aan_node} as AAN")

        # successfully found a aan. mark the item as not available anymore
        self.item_data[item_id - 1]['itemID'] = -1

        # 2. Inform the Chosen Node that it's the AAN
        auction_data = f"{item_id},{client_ip},{client_port}"  # Include client address for communication
        self.unicast_soc.send(MessageType.AUCTION_INIT, auction_data, aan_node.ip, aan_node.port)
        print(f"  [server.py] [Server.start_auction] Sent AUCTION_INIT to AAN at {aan_node.ip}:{aan_node.port}")

        # 3. Respond to Client with AAN Address
        self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, f"{aan_node.ip},{aan_node.port}", client_ip, client_port)
        print(f"  [server.py] [Server.start_auction] Sent START_AUCTION_RESPONSE to client at {client_ip}:{client_port}")

    def select_idle_node(self) -> Node | None:
        """
        Selects a single idle node from the groupview to potentially serve as an AAN or PAN.

        This method iterates through the groupview, excluding the current node itself,
        and queries the state of each node. It returns the first node found to be in the IDLE state.

        Returns:
            Node: An idle node from the groupview, or None if no idle node is found.
        """
        print(f"  [server.py] [Server.select_idle_node] Selecting an Idle Node")
        for node in self.groupview.copy(): # .copy to avoid runtimeerror
            # Iterate through the groupview set
            if node.uuid != self.uuid:  # Skip the current node itself
                print(f"  [server.py] [Server.select_idle_node] Checking node {node}")
                # Check the state of each node in groupview using self.get_node_state
                node_state = self.get_node_state(node)
                print(f"  [server.py] [Server.select_idle_node] node state is {node_state}")
                if node_state == Server.State.IDLE:
                    return node
        return None

    def get_node_state(self, node: Node) -> State:
        """
        Gets the state of a given node by sending a STATE_QUERY message.
        Uses a dedicated UnicastSocket for this operation.
        """
        print(f"  [server.py] [Server.get_node_state] Getting state of node {node.uuid} ({node.ip}:{node.port})")
        state_socket: UnicastSocket = UnicastSocket(9999)  # Use a separate socket for state queries
        # send query, then listen for a response for {timeout} seconds
        state_socket.send(MessageType.STATE_QUERY, str(self.uuid), node.ip, node.port)
        timeout: float = 1.0
        start_time: float = time.time()
        while timeout > 0:
            try:
                response: Message = state_socket.delivered.get(block=True, timeout=timeout)
                print(f"  [server.py] [Server.get_node_state] delivered queue message: {response}")
                #response: Message = self.state_response.get(block=True, timeout=timeout)
                if response.message_type == MessageType.STATE_RESPONSE and response.content.startswith(str(self.uuid)):
                    # Extract the state from the content (assuming format: "requesting_uuid,state")
                    _, state_str = response.content.split(",", 1)
                    print(f"  [server.py] [Server.get_node_state] Received state {state_str} from node {node.uuid}")
                    state_socket.close()
                    return Server.State[state_str]  # Convert string back to State enum
                else:
                    print(f"  [server.py] [Server.get_node_state] Received unexpected message: {response}")

            except Empty:
                # actual timeout is handled at the end of the function
                break
            
            timeout -= (time.time() - start_time)
            start_time = time.time()

        # handle timeout
        print(f"  [server.py] [Server.get_node_state] No response from node {node.uuid} within timeout")
        state_socket.close()
        if node in self.groupview.copy():
            self.groupview.remove(node)
            self.send_groupview_update()  # Send groupview update after removing
        return Server.State.UNINITIALIZED  # Or some other default state if no response

    def initialize_auction(self, item_id: str, client_ip: str, client_port: int) -> None:
        """
        Initializes the auction when the server is the chosen AAN.

        Args:
            item_id: The ID of the item to be auctioned.
            client_ip: The IP address of the client that initiated the auction.
            client_port: The port number of the client that initiated the auction.
        """
        print(f"  [server.py] [Server.initialize_auction] Initializing auction for item '{item_id}'")

        # 1. Store Auction Information
        self.item_id = item_id  # Store the item ID
        self.clients = []  # Initialize an empty list to store clients participating in the auction
        self.client_address = (client_ip, client_port)  # Store the address of the client initiating the auction
        # self.clients.append(self.client_address) #Not used

        self.state = Server.State.AAN  # Update the server's state to AAN

        numeric_item_id = int(self.item_id)  # Convert item ID to an integer for comparison
        self.highest_bid: int = 0  # Initialize the highest bid to 0
        # Find the initial price of the item from the item_data
        for item in self.item_data:
            if item["itemID"] == numeric_item_id:
                self.highest_bid = int(item["price"])
                break

        self.highest_bidder = None  # Initialize the highest bidder to None

        # 2. Request a PAN from INM
        # Send a PAN_REQUEST message to the INM, including the AAN's UUID, IP, and port
        if self.inm is None:
            print(f"  [server.py] [Server.initialize_auction] No INM available to request PAN.")
        else:
            self.unicast_soc.send(MessageType.PAN_REQUEST, f"{str(self.uuid)},{self.ip},{self.port}", self.inm.ip, self.inm.port)
        print(f"  [server.py] [Server.initialize_auction] Sent PAN_REQUEST request to INM (including IP and port)")

        # 3. Start Auction Timer
        self.auction_end_time = time.time() + 60  # Set the auction end time to 60 seconds from now
        self.auction_timer = threading.Timer(60,
                                             self.finalize_auction)  # Create a timer that calls finalize_auction after 60 seconds
        self.auction_timer.name = "AuctionTimerThread"  # Set the name of the timer thread
        self.auction_timer.start()  # Start the auction timer
        print(
            f"  [server.py] [Server.initialize_auction] Starting auction timer {60} seconds from now at {self.auction_end_time}")

    def request_pan(self, aan_data: str) -> None:
        """
        Handles the PAN_REQUEST request when the server is the INM.
        Selects an idle node to become the PAN, informs the chosen node,
        and sends PAN information to the requesting AAN.

        Args:
            aan_data: A string containing the AAN's UUID, IP, and port, separated by commas.
        """
        aan_uuid, aan_ip, aan_port = aan_data.split(",")  # Parse the AAN's data
        print(
            f"  [server.py] [Server.request_pan] Received PAN_REQUEST request from AAN {aan_uuid} ({aan_ip}:{aan_port})")

        # 1. Select an Idle Node as PAN
        pan_node = self.select_idle_node()  # Call a method to select an idle node from the groupview

        if pan_node is None:
            print(f"  [server.py] [Server.request_pan] No idle nodes available for PAN.")
            # Inform the AAN that no PAN could be assigned
            self.unicast_soc.send(MessageType.PAN_FAILURE, "Noidlenodesavailable", aan_ip, int(aan_port))
            return

        # 2. Inform the Chosen Node that it's the PAN
        #    Include AAN's UUID, IP, and port in the PAN_RESPONSE message
        pan_data = f"{aan_uuid},{aan_ip},{aan_port}"
        self.unicast_soc.send(MessageType.PAN_RESPONSE, pan_data, pan_node.ip, pan_node.port)
        print(
            f"  [server.py] [Server.request_pan] Sent PAN_RESPONSE to PAN at {pan_node.ip}:{pan_node.port} (including AAN IP and port)")

        # 3. Send PAN_INFO message to AAN
        #    Inform the AAN about the selected PAN, including its IP, port, and UUID
        self.unicast_soc.send(MessageType.PAN_INFO, f"{pan_node.ip},{pan_node.port},{pan_node.uuid}", aan_ip,
                              int(aan_port))
        print(f"  [server.py] [Server.request_pan] Sent PAN_INFO to AAN at {aan_ip}:{aan_port}")

        # 4. Trigger state replication from AAN to new PAN
        #    Send a REPLICATE_STATE_REQUEST to the AAN to initiate the state replication process
        self.unicast_soc.send(MessageType.REPLICATE_STATE_REQUEST, "", aan_ip, int(aan_port))
        print(f"  [server.py] [Server.request_pan] Sent REPLICATE_STATE_REQUEST to AAN at {aan_ip}:{aan_port}")

    def set_as_pan(self, pan_data: str) -> None:
        """
        Handles the PAN_RESPONSE message when the server is the chosen PAN.
        Updates the server's state to PAN and stores the AAN's information.

        Args:
            pan_data: A string containing the AAN's UUID, IP, and port, separated by commas.
        """
        aan_uuid, aan_ip, aan_port = pan_data.split(",")  # Parse the AAN's data
        print(f"  [server.py] [Server.set_as_pan] Designated as PAN for AAN {aan_uuid} ({aan_ip}:{aan_port})")
        self.state = Server.State.PAN  # Update the server's state to PAN

        # Store AAN information for potential future use (e.g., communication, failure handling)
        self.aan_node = Server.Node(aan_ip, int(aan_port), uuid.UUID(aan_uuid))

        # Store AAN information for potential future use
        self.aan_node = Server.Node(aan_ip, int(aan_port), uuid.UUID(aan_uuid))

    def join_auction(self, item_id: str, client_uuid: str, client_ip: str, client_port: int) -> None:
        """
        Handles a JOIN_AUCTION_REQUEST from a client.

        This method is called when an AAN receives a request from a client to join an ongoing auction.

        Args:
            item_id (str): The ID of the item for which the auction join is requested.
            client_uuid (str): The UUID of the client requesting to join.
            client_ip (str): The IP address of the client.
            client_port (int): The port number of the client.
        """
        print(
            f"  [server.py] [Server.join_auction] Received JOIN_AUCTION_REQUEST for item {item_id} from {client_ip}:{client_port}")

        if item_id == self.item_id:
            # Add the client to the list of clients
            self.clients.append((client_ip, client_port, client_uuid))
            # Replicate the updated state to the PAN
            self.replicate_state()
            # Send auction information to the client
            auction_info = f"{self.item_id},{self.highest_bid},{self.highest_bidder}"
            self.unicast_soc.send(MessageType.JOIN_AUCTION_RESPONSE, auction_info, client_ip, client_port)
            print(
                f"  [server.py] [Server.join_auction] Sent auction info to newly joined client {client_uuid}: {auction_info}")
        else:
            # Send a failure response to the client
            self.unicast_soc.send(MessageType.JOIN_AUCTION_RESPONSE, "failed", client_ip, client_port)
            print(f"  [server.py] [Server.join_auction] Client {client_uuid} failed to join auction for item {item_id}")

    def replicate_state(self) -> None:
        """
        Sends the current auction state to the PAN (Passive Auctioneer Node).

        This method is used by an AAN to replicate its current auction state to the PAN.
        The state includes the item_id, highest bid, highest bidder, a list of connected clients, and the remaining auction time.
        The client list is formatted as a semicolon-separated string of "ip:port:uuid" entries.

        The message is sent as a REPLICATE_STATE message to the PAN's IP and port.
        """
        if self.state == Server.State.AAN:
            # Convert the client list to a string representation
            client_list_str = ";".join([f"{c[0]}:{c[1]}:{c[2]}" for c in self.clients])
            remaining_time = int(self.auction_end_time - time.time())  # Convert to integer
            if remaining_time < 0:  # Ensure remaining_time is not negative
                remaining_time = 0
            message_content = f"{self.item_id},{self.highest_bid},{self.highest_bidder},{client_list_str},{remaining_time}"
            if self.pan_node == None:
                print(f"  [server.py] [Server.replicate_state] PAN node is None, cannot replicate state")
            else:
                self.unicast_soc.send(MessageType.REPLICATE_STATE, message_content, self.pan_node.ip, self.pan_node.port)
            print(f"  [server.py] [Server.replicate_state] Replicated state to PAN: {message_content}")

    def return_to_idle(self) -> None:
        """
        Resets the server to the IDLE state and clears auction-related data.

        This method is called to transition the server back to its default IDLE state after an auction has ended or
        when a PAN is no longer needed.
        It clears auction-specific data such as item_id, clients, client_address, highest_bid, and highest_bidder.

        Additionally, it checks if the server has the highest UUID in the groupview after returning to idle.
        If it does, it triggers an election to potentially become the new INM.
        """
        print(f"  [server.py] [Server.return_to_idle] Server {self.uuid} returning to IDLE")
        self.state = Server.State.IDLE

        # Clear auction data
        self.item_id = None
        self.clients = []
        self.client_address = None
        #self.highest_bid = None
        self.highest_bid = -1
        self.highest_bidder = None

        if self.pan_node:  # This was an AAN
            self.pan_node = None
        elif self.aan_node:  # This was a PAN
            self.aan_node = None

        # make it return to idle pool in groupview
        # Check if the current node has the actual highest UUID, if so, trigger an election
        if self.groupview:
            highest_uuid = max(node.uuid for node in self.groupview)
            if self.uuid == highest_uuid:
                print(
                    f"  [server.py] [Server.return_to_idle] This node has the highest UUID, triggering election")
                self.inm = None  # Reset INM before starting election
                self.start_election()
                self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
                self.inm_thread.start()
                return

    def finalize_auction(self) -> None:
        """
        As AAN: Finalizes the auction process and notifies participants.
        """
        print(f"  [server.py] [Server.finalize_auction] Finalizing auction for item {self.item_id}")

        # 1. Inform Clients 
        for client_ip, client_port, client_uuid in self.clients:
            message = f"{self.item_id},{self.highest_bid},{self.highest_bidder if self.highest_bidder else 'None'},{'Winner' if self.highest_bidder == client_uuid else 'Loser'}"
            self.unicast_soc.send(MessageType.AUCTION_END, message, client_ip, client_port)

        # 2. Inform PAN
        if self.pan_node:
            self.unicast_soc.send(MessageType.AUCTION_END, "", self.pan_node.ip, self.pan_node.port)

        # 3. Reset AAN State
        self.return_to_idle()

    def start_heartbeat_thread(self) -> None:
        """Start a single persistent heartbeat thread if not already running."""
        print(f"  [server.py] [Server.start_heartbeat_thread] Starting heartbeat thread")
        if self._heartbeat_thread is None or not self._heartbeat_thread.is_alive():
            self._heartbeat_stop_event.clear()
            self._heartbeat_thread = Thread(target=self.heartbeat_loop, name="HeartbeatThread")
            self._heartbeat_thread.daemon = True
            self._heartbeat_thread.start()

    def stop_heartbeat_thread(self) -> None:
        """Signal the heartbeat thread to stop and wait for it to finish."""
        print(f"  [server.py] [Server.stop_heartbeat_thread] Stopping heartbeat thread")
        self._heartbeat_stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join()
        self._heartbeat_thread = None

    def heartbeat_loop(self) -> None:
        """Single loop that sends heartbeats based on the server's state."""
        while not self._heartbeat_stop_event.is_set():
            # INM state: send heartbeat to idle nodes
            if self.state == Server.State.INM:
                self.send_heartbeats_to_idle_nodes_once()
            # IDLE state: send heartbeat to INM
            elif self.state == Server.State.IDLE:
                self.send_heartbeats_to_inm_once()
            # AAN state: send heartbeat to PAN
            elif self.state == Server.State.AAN:
                self.send_heartbeats_to_pan_once()
            # PAN state: send heartbeat to AAN
            elif self.state == Server.State.PAN:
                self.send_heartbeats_to_aan_once()

            # Sleep for heartbeat interval or check stop condition more frequently if needed
            self._heartbeat_stop_event.wait(self.HEARTBEAT_INTERVAL)

    def send_heartbeats_to_idle_nodes_once(self) -> None:
        """
        Sends heartbeat messages to all nodes in the groupview.
        
        This method is executed by the INM server to ensure the connectivity of nodes 
        within the groupview. It sends HEARTBEAT_REQUEST messages to all nodes, removes 
        unresponsive nodes from the groupview, and handles nodes that are currently in 
        the AAN or PAN state separately. The updated groupview is broadcast periodically 
        to all members of the group.
    
        Notes:
        - Nodes failing to respond within the heartbeat timeout are removed from the groupview.
        - Nodes acting as AAN or PAN are kept in the groupview but have their heartbeat reset.
    
        """
        print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Starting heartbeat process for idle nodes.")
        nodes_to_remove: set[Server.Node] = set()
        for node in self.groupview.copy():
            if node.uuid != self.uuid:
                try:
                    print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Sending HEARTBEAT_REQUEST to node {node}")
                    self.unicast_soc.send(MessageType.HEARTBEAT_REQUEST, str(self.uuid), node.ip, node.port)
    
                    # Add node to groupview if missing (e.g., edge case handling)
                    self.groupview.add(node)
                except Exception as e:
                    print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] ERROR: Failed to send heartbeat to node {node}: {e}")
    
                # Check if node's last heartbeat exceeds timeout threshold
                if time.time() - node.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                    print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Node {node} has exceeded heartbeat timeout.")
                    
                    # Handle nodes in AAN or PAN state: keep but reset heartbeat
                    if node.uuid != self.uuid:
                        node_state = self.get_node_state(node)
                        if node_state in [Server.State.AAN, Server.State.PAN]:
                            print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Node {node} is in AAN/PAN state. Keeping it in groupview and resetting heartbeat.")
                            node.last_heartbeat = time.time()
                        else:
                            # Mark node for removal
                            nodes_to_remove.add(node)
    
        # Process nodes marked for removal
        for node in nodes_to_remove:
            if node in self.groupview:
                print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Removing unresponsive node {node} from groupview.")
                self.groupview.remove(node)
                self.send_groupview_update()
    
        # Increment the heartbeat counter and broadcast groupview periodically
        self.heartbeat_counter += 1
        if self.heartbeat_counter % self.GROUPVIEW_UPDATE_HEARTBEAT_INTERVAL == 0:
            print(f"  [server.py] [Server.send_heartbeats_to_idle_nodes_once] Broadcasting updated groupview to all nodes.")
            self.send_groupview_update()

    def send_heartbeats_to_inm_once(self) -> None:
        """
        Sends a heartbeat message to the current INM.

        If the INM is this node, it forces the state to INM.
        If the INM is unreachable or unresponsive (determined by heartbeat timeout),
        it initiates an election process if this node has the highest UUID among remaining idle nodes.
        """
        print(f"    [server.py] [Server.send_heartbeats_to_inm_once] Sending heartbeat to INM")
        # If this node is the INM, ensure the state reflects this
        if self.inm and self.inm.uuid == self.uuid:
            print(f"  [server.py] [Server.send_heartbeats_to_inm_once] Forcing state update to INM")
            self.state = Server.State.INM

        # Proceed if the INM is known and has a valid port
        if self.inm and self.inm.port > 0:
            try:
                # Send a heartbeat request to the INM
                self.unicast_soc.send(MessageType.HEARTBEAT_REQUEST, str(self.uuid), self.inm.ip, self.inm.port)
            except Exception as e:
                print(f"Heartbeat send failed: {e}")

            # TODO: could be buggy, test further?
            # If this node has the highest UUID in the groupview, start an election
            if self.groupview:
                highest_uuid = max(node.uuid for node in self.groupview)
                if self.uuid == highest_uuid:
                    print(
                        f"  [server.py] [Server.send_heartbeats_to_inm_once] This node has the highest UUID")
                    self.inm = None  # Reset INM before starting election
                    self.start_election()
                    self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
                    self.inm_thread.start()
                    return

            # Check if the INM's heartbeat has timed out
            if time.time() - self.inm.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                print(f"  [server.py] [Server.send_heartbeats_to_inm_once] INM heartbeat timeout")

                # Remove the unresponsive INM from the groupview
                temp_groupview = self.groupview.copy()
                for node in temp_groupview:
                    if node.uuid == self.inm.uuid:
                        self.groupview.remove(node)
                        print(
                            f"  [server.py] [Server.send_heartbeats_to_inm_once] Removed INM {self.inm.uuid} from groupview")
                        self.send_groupview_update()
                        break

                # After INM removal, check if this node has the highest UUID among idle nodes (excluding AAN and PAN)
                if self.groupview:
                    idle_nodes: list[Server | Server.Node] = []
                    # if self is idle, add self to idle_nodes
                    if self.state not in [Server.State.AAN, Server.State.PAN]:
                        idle_nodes.append(self)
                    # Add other idle nodes to idle_nodes
                    for node in self.groupview.copy():
                        if node.uuid != self.uuid:
                            node_state = self.get_node_state(node)
                            if node_state not in [Server.State.AAN, Server.State.PAN]:
                                idle_nodes.append(node)
                    # If there are any idle nodes, check for the highest UUID and potentially start an election
                    if idle_nodes:
                        highest_uuid = max(node.uuid for node in idle_nodes)
                        if self.uuid == highest_uuid:
                            print(
                                f"  [server.py] [Server.send_heartbeats_to_inm_once] This node has the highest UUID among idle nodes after INM removal.")
                            self.inm = None  # Reset INM before starting election
                            self.start_election()
                            self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
                            self.inm_thread.start()
                        else:
                            print(
                                f"  [server.py] [Server.send_heartbeats_to_inm_once] This node does not have the highest UUID among idle nodes. Waiting for new INM.")
                            self.inm = None  # Reset INM in case a new one is elected
                    # If no idle nodes are found, reset INM and wait
                    else:
                        print(
                            f"  [server.py] [Server.send_heartbeats_to_inm_once] No idle nodes found. Waiting for new INM.")
                        # self.inm = None  # Reset INM in case a new one is elected
        # If the INM is not set or invalid, start an election
        else:
            # this case happens when multiple nodes including INM crash at once
            # trigger election because no INM? could use find_INM first?
            self.start_election()
            self.inm_thread: Thread = Thread(target=self.declare_inm, args=(lambda: self.received_ack,))
            self.inm_thread.start()
            print("INM not set or invalid; skipping heartbeat send.")

    def send_heartbeats_to_pan_once(self) -> None:
        """Sends a heartbeat to the PAN and requests a new PAN if no response is received within the timeout."""
        if self.pan_node:
            try:
                print(
                    f"  [server.py] [Server.send_heartbeats_to_pan_once] Sending heartbeat to PAN")

                self.unicast_soc.send(MessageType.HEARTBEAT_REQUEST, str(self.uuid), self.pan_node.ip,
                                      self.pan_node.port)
            except Exception as e:
                print(f"    [server.py] [Server.send_heartbeats_to_pan_once] Heartbeat send to PAN failed: {e}")
            if time.time() - self.pan_node.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                print(f"  [server.py] [Server.send_heartbeats_to_pan_once] PAN heartbeat timeout")
                self.request_new_pan()

    def send_heartbeats_to_aan_once(self) -> None:
        """Sends a heartbeat to the AAN and promotes to AAN if no response is received within the timeout."""
        print(f"  [server.py] [Server.send_heartbeats_to_aan_once] Sending heartbeat to AAN")

        if self.aan_node:
            try:
                self.unicast_soc.send(MessageType.HEARTBEAT_REQUEST, str(self.uuid), self.aan_node.ip,
                                      self.aan_node.port)
            except Exception as e:
                print(f"    [server.py] [Server.send_heartbeats_to_aan_once] Heartbeat send to AAN failed: {e}")
            if time.time() - self.aan_node.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                print(f"  [server.py] [Server.send_heartbeats_to_aan_once] AAN heartbeat timeout")
                self.promote_to_aan()

    def promote_to_aan(self) -> None:
        """Handles the PAN's transition to AAN upon AAN failure."""
        print(f"  [server.py] [Server.promote_to_aan] PAN {self.uuid} promoting to AAN")

        self.state = Server.State.AAN
        # Reset aan_node and pan_node as this PAN is now the new AAN
        self.aan_node = None
        self.pan_node = None

        # Inform clients about the new AAN address
        for client_ip, client_port, _ in self.clients:
            self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, f"{self.ip},{self.port}", client_ip, client_port)
            print(
                f"  [server.py] [Server.promote_to_aan] Sent START_AUCTION_RESPONSE (new AAN info) to client at {client_ip}:{client_port}")

        # Request a new PAN from the INM
        self.request_new_pan()

    def request_new_pan(self) -> None:
        """
        Requests a new PAN from the INM. Sends a PAN_REQUEST message to the INM containing the AAN's UUID, IP, and port.
        """
        if self.state == Server.State.AAN:
            if self.inm == None:
                print(f"  [server.py] [Server.request_new_pan] No INM available to request PAN.")
            else:
                self.unicast_soc.send(MessageType.PAN_REQUEST, f"{str(self.uuid)},{self.ip},{self.port}", self.inm.ip, self.inm.port)
            print(f"  [server.py] [Server.request_new_pan] Sent PAN_REQUEST request to INM (including IP and port)")

    def send_groupview_update(self) -> None:
        """Sends the current groupview to all nodes in the group. Only applicable to the INM server."""
        if self.state == Server.State.INM:
            # Construct the groupview string: "ip:port:uuid;ip:port:uuid;..."
            groupview_str = ";".join([f"{node.ip}:{node.port}:{node.uuid}" for node in self.groupview])

            # handle reliable multicast through acks and retransmissions
            # -> doesnt need deduplication because the messages are idempotent
            self.waiting_on_groupview_ack: list[uuid.UUID] = [node.uuid for node in self.groupview]
            groupview_ack_thread: Thread = Thread(target=self.groupview_ack, args=(groupview_str,), name="GroupviewAckThread")
            groupview_ack_thread.start()

            print(f"  [server.py] [Server.send_groupview_update] Sending groupview update: {groupview_str}")
            # Send the groupview update to all nodes via multicast
            self.idle_grp_sock.send(MessageType.GROUPVIEW_UPDATE, groupview_str)    # ack handled right above

    def groupview_ack(self, groupview_str: str) -> None:
        time.sleep(1)
        unacked_nodes: list[Server.Node] = [node for node in self.groupview if node.uuid in self.waiting_on_groupview_ack]
        for node in unacked_nodes:
            print(f"  [server.py] [Server.groupview_ack] Sending GROUPVIEW_UPDATE to unacknowledged node {node}")
            self.unicast_soc.send(MessageType.GROUPVIEW_UPDATE, groupview_str, node.ip, node.port)




# used for dummy testing
if __name__ == "__main__":
    # Usage: python server.py <port> [<uuid>]
    #myserver: Server = Server(5384)
    if len(sys.argv) == 2:
        try:
            port = int(sys.argv[1])
            myserver: Server = Server(port)
        except ValueError:
            print("Error: Port must be an integer.")
            sys.exit(1)
    elif len(sys.argv) == 3:
        try:
            port = int(sys.argv[1])
            set_uuid = int(sys.argv[2])
            myserver: Server = Server(port, set_uuid)
        except ValueError:
            print("Error: Port and uuid must be integers.")
            sys.exit(1)
    else:
        print("Usage: python server.py <port> [<uuid>]")
        sys.exit(1)
    

    