# uid management
# cli
# query available items
# start auction
# join auction
# bid on item
import json
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
        AAN = 4
        PAN = 5


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
        # Simple item list (list of dictionaries)
        self.item_data: list[dict] = [
            {"itemID": 1, "itemname": "Master Sword", "price": 1000},
            {"itemID": 2, "itemname": "Hylian Shield", "price": 500},
            {"itemID": 3, "itemname": "Hookshot", "price": 300},
            {"itemID": 4, "itemname": "Boomerang", "price": 200},
        ]
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
        self.pan_node: Server.Node = None # Keep track of the assigned PAN

        self.inm_thread: Thread = Thread()  # this thread is used as a timeout for election acks
        self.received_ack: bool = False  # this bool is used to communicate with the thread

        self.info_thread: Thread = Thread(target=self.periodic_info_print)
        self.info_thread.daemon = True  # Allow the main thread to exit even if this thread is running
        self.info_thread.start()

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

    def print_info(self) -> None:
        """Prints the server's information to the console."""
        print(f"\n===== Server Info =====")
        print(f"UUID: {self.uuid}")
        print(f"State: {self.state.name}")
        print(f"IP: {self.ip}")
        print(f"Port: {self.port}")
        if self.state == Server.State.AAN:
            print(f"  PAN: {self.pan_node.uuid} ({self.pan_node.ip}:{self.pan_node.port})")
            if hasattr(self, 'item_id'):
                print(f"    Auction Item: {self.item_id}")
            if hasattr(self, 'highest_bid'):
                print(f"    Highest Bid: {self.highest_bid}")
            if hasattr(self, 'highest_bidder'):
                print(f"    Highest Bidder: {self.highest_bidder}")
            if hasattr(self, 'client_address'):
                print(f"    Client: {self.client_address}")
            if hasattr(self, 'clients'):
                print(f"    Clients: {self.clients}")
        elif self.state == Server.State.PAN:
            print(f"  Assigned to AAN: {self.aan_node.uuid} ({self.aan_node.ip}:{self.aan_node.port})")
            if hasattr(self, 'item_id'):
                print(f"    Auction Item: {self.item_id}")
            if hasattr(self, 'highest_bid'):
                print(f"    Highest Bid: {self.highest_bid}")
            if hasattr(self, 'highest_bidder'):
                print(f"    Highest Bidder: {self.highest_bidder}")
            if hasattr(self, 'client_address'):
                print(f"    Client: {self.client_address}")
            if hasattr(self, 'clients'):
                print(f"    Clients: {self.clients}")
        print(f"=======================\n")

    def periodic_info_print(self) -> None:
        """Periodically prints the server's information."""
        while True:
            self.print_info()
            time.sleep(5)

    def get_available_items_from_api(self) -> list[dict]:
        # In a real scenario, you'd query an external API
        # Here, we just return the simple item_data list
        return self.item_data

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
            if msg.src_port != self.port:
                self.state = Server.State.IDLE
                print(f"    [server.py] [Server.message_parser] DECLARE_INM SERVER {self.port} back to IDLE")
            self.inm = Server.Node(msg.src_ip, msg.src_port, uuid.UUID(msg.content))
            print(f"    [server.py] [Server.message_parser] DECLARE_INM {self.inm}")
        elif msg.message_type == MessageType.TEST:
            print(f"    [server.py] [Server.message_parser] TEST_MESSAGE")
        elif msg.message_type == MessageType.CONNECT_REQUEST:
            if self.state == Server.State.INM:
                print(f"    [server.py] [Server.message_parser] CONNECT_REQUEST")
                self.unicast_soc.send(
                    MessageType.CONNECT_RESPONSE,
                    f"{self.ip}:{self.port}",  # Send INM's IP and port
                    msg.src_ip,
                    msg.src_port,
                )
        elif msg.message_type == MessageType.STATE_QUERY:
            print(f"    [server.py] [Server.message_parser] STATE_QUERY")
            self.unicast_soc.send(MessageType.STATE_RESPONSE, self.state.name, msg.src_ip, msg.src_port)
        elif msg.message_type == MessageType.LIST_ITEMS_REQUEST:
            if self.state == Server.State.INM:
                print(f"    [server.py] [Server.message_parser] LIST_ITEMS_REQUEST")
                # Query external API for available items
                available_items = self.get_available_items_from_api()  # TODO Implement this
                # Format the item list as a string
                items_str = ""
                for item in available_items:
                    items_str += f"{item['itemID']},{item['itemname']},{item['price']};"
                # Remove the trailing semicolon
                items_str = items_str.rstrip(";").replace(" ","") # TODO has to be done this way because we split messages on space
                # Send response to client
                self.unicast_soc.send(
                    MessageType.LIST_ITEMS_RESPONSE,
                    items_str,
                    msg.src_ip,
                    msg.src_port,
                )
        elif msg.message_type == MessageType.START_AUCTION_REQUEST:
            if self.state == Server.State.INM:
                print(f"    [server.py] [Server.message_parser] START_AUCTION_REQUEST")
                self.start_auction(msg.content, msg.src_ip, msg.src_port)
        elif msg.message_type == MessageType.AUCTION_INIT:
            if self.state == Server.State.IDLE:  # Only idle nodes can become AANs
                print(f"    [server.py] [Server.message_parser] AUCTION_INIT")
                item_id, client_ip, client_port = msg.content.split(",")
                self.initialize_auction(item_id, client_ip, int(client_port))
        elif msg.message_type == MessageType.PAN_REQUEST:
            if self.state == Server.State.INM:
                print(f"    [server.py] [Server.message_parser] PAN_REQUEST")
                self.request_pan(msg.content)
        elif msg.message_type == MessageType.PAN_RESPONSE:
            if self.state == Server.State.IDLE:  # Only idle nodes can become PANs
                print(f"    [server.py] [Server.message_parser] PAN_RESPONSE")
                self.set_as_pan(msg.content)
        elif msg.message_type == MessageType.PAN_INFO:
            if self.state == Server.State.AAN:
                print(f"    [server.py] [Server.message_parser] PAN_INFO")
                # Store the PAN's information
                pan_ip, pan_port, pan_uuid = msg.content.split(",")
                self.pan_node = Server.Node(pan_ip, int(pan_port), uuid.UUID(pan_uuid))
                print(f"    [server.py] [Server.message_parser] AAN received PAN information: {self.pan_node}")
        elif msg.message_type == MessageType.JOIN_AUCTION_REQUEST:
            if self.state == Server.State.AAN:
                print(f"    [server.py] [Server.message_parser] JOIN_AUCTION_REQUEST")
                item_id, client_uuid = msg.content.split(",")
                # Only process if this AAN is responsible for the item_id
                if item_id == self.item_id:
                    self.join_auction(item_id, client_uuid, msg.src_ip, msg.src_port)
        elif msg.message_type == MessageType.BID_REQUEST:
            if self.state == Server.State.AAN:
                print(f"    [server.py] [Server.message_parser] BID_REQUEST")
                item_id, bid_amount, client_uuid = msg.content.split(",")
                bid_amount = int(bid_amount)

                if item_id == self.item_id and bid_amount > self.highest_bid:
                    self.highest_bid = bid_amount
                    self.highest_bidder = client_uuid
                    self.replicate_state()  # Replicate the updated state to the PAN
                    self.unicast_soc.send(MessageType.BID_RESPONSE, "Bid accepted", msg.src_ip, msg.src_port)
                    print(
                        f"    [server.py] [Server.message_parser] Accepted bid for item {item_id} from {client_uuid} for {bid_amount}")
                else:
                    self.unicast_soc.send(MessageType.BID_RESPONSE, "Bid rejected", msg.src_ip, msg.src_port)
                    print(
                        f"    [server.py] [Server.message_parser] Rejected bid for item {item_id} from {client_uuid} for {bid_amount}")
        elif msg.message_type == MessageType.REPLICATE_STATE:
            if self.state == Server.State.PAN:
                print(f"    [server.py] [Server.message_parser] [PAN] REPLICATE_STATE ")
                item_id, highest_bid, highest_bidder, client_list_str = msg.content.split(",", 3)
                self.item_id = item_id
                self.highest_bid = highest_bid
                self.highest_bidder = highest_bidder if highest_bidder != "None" else None

                # Update the client list
                self.clients = []
                if client_list_str:  # Check if the string is not empty
                    for client_str in client_list_str.split(";"):
                        client_ip, client_port, client_uuid = client_str.split(":")
                        self.clients.append((client_ip, int(client_port), client_uuid))

                print(
                    f"    [server.py] [Server.message_parser] Updated PAN state: item_id={item_id}, highest_bid={self.highest_bid}, highest_bidder={self.highest_bidder}, clients={self.clients}")
        else:
            print("     [server.py] [Server.message_parser] ERROR: Unknown message")

    def start_auction(self, item_id: str, client_ip: str, client_port: int) -> None:
        """
        Handles the START_AUCTION_REQUEST when the server is the INM.
        """
        print(f"  [server.py] [Server.start_auction] Received START_AUCTION_REQUEST for item '{item_id}' from {client_ip}:{client_port}")

        # 1. Select an Idle Node as AAN
        aan_node = self.select_idle_node()

        if aan_node is None:
            print(f"  [server.py] [Server.start_auction] No idle nodes available.")
            self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, "ERROR:Noidlenodesavailable", client_ip, client_port)
            return
        print(f"  [server.py] [Server.start_auction] Selected {aan_node} as AAN")
        # 2. Inform the Chosen Node that it's the AAN
        auction_data = f"{item_id},{client_ip},{client_port}"  # Include client address for communication
        self.unicast_soc.send(MessageType.AUCTION_INIT, auction_data, aan_node.ip, aan_node.port)
        print(f"  [server.py] [Server.start_auction] Sent AUCTION_INIT to AAN at {aan_node.ip}:{aan_node.port}")

        # 3. Respond to Client with AAN Address
        self.unicast_soc.send(MessageType.START_AUCTION_RESPONSE, f"{aan_node.ip},{aan_node.port}", client_ip, client_port)
        print(f"  [server.py] [Server.start_auction] Sent START_AUCTION_RESPONSE to client at {client_ip}:{client_port}")

    def select_idle_node(self) -> Node:
        """
        Selects a single idle node from the groupview.
        """
        print(f"  [server.py] [Server.select_idle_node] Selecting an Idle Node")
        for node in self.groupview:
            # Iterate through the groupview set directly
            print(f"  [server.py] [Server.select_idle_node] Checking node {node}")
            if node.uuid != self.uuid:  # Skip the current node itself
                # Check the state of each node in groupview using self.get_node_state
                node_state = self.get_node_state(node)
                print(f"  [server.py] [Server.select_idle_node] node state is {node_state}")
                if node_state == Server.State.IDLE:
                    return node
        return None

    def get_node_state(self, node: Node) -> State:
        """
        Gets the state of a given node by sending a STATE_QUERY message.
        """
        print(f"  [server.py] [Server.get_node_state] Getting state of node {node.uuid}")

        # Send a STATE_QUERY message to the node
        self.unicast_soc.send(MessageType.STATE_QUERY, "", node.ip, node.port)

        # Wait for a response (with a timeout)
        ready, _, _ = select.select([self.unicast_soc], [], [], 1.0)  # 1 second timeout

        if ready:
            response: Message = ready[0].receive()
            if response.message_type == MessageType.STATE_RESPONSE:
                print(f"  [server.py] [Server.get_node_state] Received state {response.content} from node {node.uuid}")
                return Server.State[response.content]  # Convert string back to State enum
            else:
                print(f"  [server.py] [Server.get_node_state] Invalid response from node {node.uuid}")

        print(f"  [server.py] [Server.get_node_state] No response from node {node.uuid} within timeout")
        return Server.State.UNINITIALIZED  # Or some other default state if no response

    def initialize_auction(self, item_id: str, client_ip: str, client_port: int) -> None:
        """
        Initializes the auction when the server is the chosen AAN.

        """
        print(f"  [server.py] [Server.initialize_auction] Initializing auction for item '{item_id}'")

        # 1. Store Auction Information
        self.item_id = item_id
        self.clients = []
        self.client_address = (client_ip, client_port) # Store client address for communication
        #self.clients.append(self.client_address)

        self.state = Server.State.AAN # Update the state to AAN

        numeric_item_id = int(self.item_id) # Now storing as integer
        self.highest_bid = 0
        for item in self.item_data:
            if item["itemID"] == numeric_item_id:
                self.highest_bid = item["price"]
                break

        self.highest_bidder = None

        # 2. Request a PAN from INM
        self.unicast_soc.send(MessageType.PAN_REQUEST, f"{str(self.uuid)},{self.ip},{self.port}", self.inm.ip, self.inm.port)
        print(f"  [server.py] [Server.initialize_auction] Sent PAN_REQUEST request to INM (including IP and port)")

    def request_pan(self, aan_data: str) -> None:
        """
        Handles the PAN_REQUEST request when the server is the INM.
        Receives AAN's UUID, IP, and port.
        """
        aan_uuid, aan_ip, aan_port = aan_data.split(",")
        print(
            f"  [server.py] [Server.request_pan] Received PAN_REQUEST request from AAN {aan_uuid} ({aan_ip}:{aan_port})")

        # 1. Select an Idle Node as PAN
        pan_node = self.select_idle_node()

        if pan_node is None:
            print(f"  [server.py] [Server.request_pan] No idle nodes available for PAN.")
            # Inform the AAN that no PAN could be assigned
            self.unicast_soc.send(MessageType.PAN_FAILURE, "No idle nodes available", aan_ip, int(aan_port))
            return

        # 2. Inform the Chosen Node that it's the PAN
        #    Include AAN's IP and port in the PAN_RESPONSE
        pan_data = f"{aan_uuid},{aan_ip},{aan_port}"
        self.unicast_soc.send(MessageType.PAN_RESPONSE, pan_data, pan_node.ip, pan_node.port)
        print(
            f"  [server.py] [Server.request_pan] Sent PAN_RESPONSE to PAN at {pan_node.ip}:{pan_node.port} (including AAN IP and port)")

        # 3. Send PAN_INFO message to AAN
        self.unicast_soc.send(MessageType.PAN_INFO, f"{pan_node.ip},{pan_node.port},{pan_node.uuid}", aan_ip, int(aan_port))
        print(f"  [server.py] [Server.request_pan] Sent PAN_INFO to AAN at {aan_ip}:{aan_port}")

    def set_as_pan(self, pan_data: str) -> None:
        """
        Handles the PAN_RESPONSE message when the server is the chosen PAN.
        """
        aan_uuid, aan_ip, aan_port = pan_data.split(",")
        print(f"  [server.py] [Server.set_as_pan] Designated as PAN for AAN {aan_uuid} ({aan_ip}:{aan_port})")
        self.state = Server.State.PAN
        # Store AAN information for potential future use
        self.aan_node = Server.Node(aan_ip, int(aan_port), uuid.UUID(aan_uuid))

    def join_auction(self, item_id: str, client_uuid: str, client_ip: str, client_port: int) -> None:
        """
        Handles a JOIN_AUCTION_REQUEST from a client.
        """
        print(f"  [server.py] [Server.join_auction] Received JOIN_AUCTION_REQUEST for item {item_id} from {client_ip}:{client_port}")

        if item_id == self.item_id: # TODO: check if client already in? atm just gets added again but unproblematic
            # Add the client to the list of clients
            self.clients.append((client_ip, client_port, client_uuid))
            # Replicate the updated state to the PAN
            self.replicate_state()
            # Send a success response to the client
            # Send auction information to the client
            auction_info = f"{self.item_id},{self.highest_bid},{self.highest_bidder}"
            self.unicast_soc.send(MessageType.JOIN_AUCTION_RESPONSE, auction_info, client_ip, client_port)
            print(
                f"  [server.py] [Server.join_auction] Sent auction info to newly joined client {client_uuid}: {auction_info}")
        else:
            # Send a failure response to the client
            self.unicast_soc.send(MessageType.JOIN_AUCTION_RESPONSE, "failed", client_ip, client_port)
            print(f"  [server.py] [Server.join_auction] Client {client_uuid} failed to join auction for item {item_id}")

    def replicate_state(self):
        """Sends the current auction state to the PAN, including the client list."""
        if self.state == Server.State.AAN:
            # Convert the client list to a string representation
            client_list_str = ";".join([f"{c[0]}:{c[1]}:{c[2]}" for c in self.clients])
            message_content = f"{self.item_id},{self.highest_bid},{self.highest_bidder},{client_list_str}"
            self.unicast_soc.send(MessageType.REPLICATE_STATE, message_content, self.pan_node.ip, self.pan_node.port)
            print(f"  [server.py] [Server.replicate_state] Replicated state to PAN: {message_content}")

# used for dummy testing
if __name__ == "__main__":
    myserver: Server = Server(5384)