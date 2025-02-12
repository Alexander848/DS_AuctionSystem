
from typing import Callable
import uuid
import sys
import time
from threading import Thread
from middleware import MessageType
from middleware import Message
from middleware.unicast import UnicastSocket
from middleware.multicast import MulticastSocket
from middleware import get_my_ip

class Client:
    """
    The Client class manages interactions with an auction system via
    unicast and multicast communication. It allows users to list available
    items, start auctions, join auctions, place bids, and view client
    information. It also listens for messages and updates auction states.
    """
    
    def __init__(self, port: int) -> None:
        self.uuid: uuid.UUID = uuid.uuid4()
        self.ip: str = get_my_ip()
        self.port: int = port
        self.joined_auctions: dict[str, dict] = {}  # Store joined auctions

        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)
        self.multicast_soc: MulticastSocket = MulticastSocket(self.port)
        #self.inm_address: tuple[str, int] = ("", -1)  # (IP, port) of the INM
        # self.inm_unicast_soc: UnicastSocket = None  # Socket for persistent INM connection 
        
        self.listener_thread: Thread = Thread(target=self.listen_for_messages)
        self.listener_thread.daemon = True  
        self.listener_thread.start()
        
        self.main()

    def main(self):
        while True:
            self.cli()

    def cli(self):
        """
        Command Line Interface (CLI) for handling user commands 
        such as listing items, starting/joining auctions, placing bids, and exiting.
        """
        while True:
            # removed connect from input
            command = input("Enter command (list, start <item_id>, join <item_id>, bid <item_id> <amount>, exit): \n")
            command_parts = command.split()
    
            if command_parts:
                action = command_parts[0]
    
                # removed connect case
                
                # Handle the 'list' command - display available items.
                if action == "list":
                    self.list_items()
                    break
                # Handle the 'info' command - display client's information.
                if action == "info":
                    self.display_client_info()
                    break
                # Handle the 'start' command - start an auction for a specified item.
                if action == "start":
                    if len(command_parts) == 2:
                        item_id = command_parts[1]
                        self.start_auction(item_id)
                    else:
                        print("Invalid start command. Usage: start <item_id>")
                    break
                # Handle the 'join' command - join an auction for a specified item.
                if action == "join":
                    if len(command_parts) == 2:
                        item_id = command_parts[1]
                        self.join_auction(item_id)
                    else:
                        print("Invalid join command. Usage: join <item_id>")
                    break
                # Handle the 'bid' command - place a bid on an item.
                if action == "bid":
                    if len(command_parts) == 3:
                        item_id = command_parts[1]
                        try:
                            bid_amount = int(command_parts[2])
                        except ValueError:
                            print("Invalid bid amount. Usage: bid <item_id> <amount>")
                            break
                        self.place_bid(item_id, bid_amount)
                    else:
                        print("Invalid bid command. Usage: bid <item_id> <amount>")
                    break
                # Handle the 'exit' command - terminate the application.
                elif action == "exit":
                    self.unicast_soc.send(MessageType.STOP_EXECUTION, "stop", self.ip, self.port)
                    self.multicast_soc.send(MessageType.STOP_EXECUTION, str(self.ip) + "," + str(self.port))
                    print("Exiting client...")
                    exit()
                else:
                    print("Invalid command.")

    # removed connect_to_inm TODO: ADD CONNECT TO INM AND USE UNICAST?

    def listen_for_messages(self):
        """
        Continuously listens for incoming messages on the unicast socket and handles them based on message type.
        - Uses the `self.unicast_soc` socket to receive messages from the server.
        - Processes different message types (e.g., LIST_ITEMS_RESPONSE, START_AUCTION_RESPONSE, etc.).
        - Updates auction state and joins or displays information based on received messages.
        """
    
        while True:
            # Listen on self.unicast_soc
            response: Message = self.unicast_soc.delivered.get()
            print(f"parsing {response}")

            if response.message_type == MessageType.LIST_ITEMS_RESPONSE:
                self.waiting_on_list_ack = False
                # Parse the string back into a list of dictionaries
                items_list = []
                items_str = response.content
                for item_str in items_str.split(";"):
                    item_id, item_name, item_price = item_str.split(
                        ","
                    )
                    items_list.append(
                        {
                            "itemID": int(item_id),
                            "itemname": item_name,
                            "price": int(item_price),
                        }
                    )
                print("Available Items:")
                print("-----------------")
                print("ID | Item Name        | Price")
                print("-----------------")
                for item in items_list:
                    print(
                        f"{item['itemID']:<2} | {item['itemname']:<16} | {item['price']}"
                    )
                print("-----------------")
            
            # Received when starting auction or when AAN changes
            elif response.message_type == MessageType.START_AUCTION_RESPONSE:
                self.waiting_on_start_auction_ack = False
                if response.content.startswith("ERROR"):
                    print(f"Failed to start auction: {response.content}")
                else:
                    aan_ip, aan_port = response.content.split(",")
                    self.aan_address = (aan_ip, int(aan_port))
                    print(f"Auction is ongoing. AAN address: {aan_ip}:{aan_port}")
            
            elif response.message_type == MessageType.JOIN_AUCTION_RESPONSE:
                self.waiting_on_join_auction_ack = False
                if response.content == "failed":
                    print(f"Failed to join auction")
                else:
                    item_id, highest_bid, highest_bidder = response.content.split(",")
                    self.aan_address = ( response.src_ip,response.src_port,) 
                    
                    # Update joined_auctions
                    self.joined_auctions[item_id] = {"highest_bid": highest_bid,"highest_bidder": highest_bidder}
                    print(f"Successfully joined auction for item {item_id}")
                    print(f"  Current highest bid: {highest_bid} (by {highest_bidder if highest_bidder != 'None' else 'no one'})")
            
            # this handling is terrible but no other way because of message format
            elif response.message_type == MessageType.BID_RESPONSE: 
                print(f"Bid response: {response.content}")
                if response.content.startswith("Bid-for"):
                    parts = response.content.split("-")
                    if len(parts) == 7:  # Bid accepted 
                        item_id = parts[2]
                        bid_amount = parts[6]
                        remaining_time = parts[8]

                        # Update joined_auctions with new bid information
                        if item_id in self.joined_auctions:
                            self.joined_auctions[item_id]["highest_bid"] = bid_amount
                            self.joined_auctions[item_id]["highest_bidder"] = str(self.uuid)
                            print(
                                f"Bid for {item_id} accepted. New highest bid: {bid_amount} by you. Time left: {remaining_time} seconds"
                            )
                    elif len(parts) == 11:  # Bid rejected 
                        item_id = parts[2]
                        bid_amount = parts[4]
                        highest_bid = parts[10]
                        remaining_time = parts[12]

                        # Update joined_auctions with new bid information
                        self.joined_auctions[item_id]["highest_bid"] = highest_bid
                        self.joined_auctions[item_id]["highest_bidder"] = "another client"
                        print(
                            f"Bid for {item_id} for {bid_amount} rejected. Current highest bid: {highest_bid} by another client. Time left: {remaining_time} seconds"
                        )
            
            elif response.message_type == MessageType.AUCTION_END:
                print(f"Auction end response: {response.content}")
                item_id, highest_bid, highest_bidder, result = response.content.split(",")
                print(f"Auction for item {item_id} has ended.")
                print(f"  Highest Bid: {highest_bid}")
                print(f"  Highest Bidder: {highest_bidder}")
                print(f"  Result: {result}")

                # Remove the auction from joined_auctions
                if item_id in self.joined_auctions:
                    del self.joined_auctions[item_id]
            
            else:
                print(f"Received unknown or invalid message: {response}")

    def display_client_info(self) -> None:
        """Displays the client's current information."""
        print("\n                    ===== Client Info =====")
        print(f"                    UUID: {self.uuid}")
        print(f"                    IP: {self.ip}")
        print(f"                    Port: {self.port}")

        # Check if AAN address is available and display it
        if hasattr(self, 'aan_address') and self.aan_address[1] != -1:
            print(f"                    AAN Address: {self.aan_address[0]}:{self.aan_address[1]}")
        else:
            print("                    AAN Address: None")

        if self.joined_auctions:
            print("                    Joined Auctions:")
            for item_id, auction_data in self.joined_auctions.items():
                print(f"                        Item ID: {item_id}")
                print(f"                        Highest Bid: {auction_data['highest_bid']}")
                print(f"                        Highest Bidder: {auction_data['highest_bidder']}")
        else:
            print("                    Joined Auctions: None")

        print("                    =======================\n")

    def multicast_retries(self, waiting: Callable[[], bool], message_type: MessageType, message_content: str, retries: int = 3) -> None:
        """
        Sends a multicast message with retries to make it reliable. Deduplication is handled in the middleware.
        """
        while waiting() and retries > 0:
            print(f"multicasting {message_type} message")
            self.multicast_soc.send(message_type, message_content)
            time.sleep(1)
            retries -= 1
            if retries == 0:
                print(f"No response for {message_type}")

    def list_items(self) -> None:
        """
        Sends a LIST_ITEMS_REQUEST message to discover available auction items.
        This message is broadcast to all servers using the multicast socket.
        """
        # acknowlegement handling

        self.waiting_on_list_ack: bool = True
        multicast_thread: Thread = Thread(target=self.multicast_retries, args=(lambda: self.waiting_on_list_ack, MessageType.LIST_ITEMS_REQUEST, str(self.uuid)))
        multicast_thread.start()

    def start_auction(self, item_id: str = "") -> None:
        """
        Sends a START_AUCTION_REQUEST message to initiate an auction for the specified item.
        This message is broadcast to all servers using the multicast socket.
        
        :param item_id: The ID of the item to start the auction for.
        """
        self.waiting_on_start_auction_ack: bool = True
        multicast_thread: Thread = Thread(target=self.multicast_retries, args=(lambda: self.waiting_on_start_auction_ack, MessageType.START_AUCTION_REQUEST, str(item_id)))
        multicast_thread.start()
        
    def join_auction(self, item_id: str) -> None:
        """
        Sends a JOIN_AUCTION_REQUEST message to participate
        in an auction for the specified item.
        This message is broadcast to all servers using the multicast socket.
        """
        message_content = f"{item_id},{self.uuid}"
        self.waiting_on_join_auction_ack: bool = True
        multicast_thread: Thread = Thread(target=self.multicast_retries, args=(lambda: self.waiting_on_join_auction_ack, MessageType.JOIN_AUCTION_REQUEST, message_content))
        multicast_thread.start()

    def place_bid(self, item_id: str, bid_amount: int):
        """
        Sends a BID_REQUEST to the AAN.
        """
        if item_id not in self.joined_auctions:
            print(f"You have not joined the auction for item {item_id}.")
            return

        message_content = f"{item_id},{bid_amount},{self.uuid}"
        self.unicast_soc.send(MessageType.BID_REQUEST, message_content, self.aan_address[0], self.aan_address[1])
        print(f"Sent BID_REQUEST for item {item_id} with amount {bid_amount} to AAN")

if __name__ == "__main__":
    # Usage: python client.py <port>
    #myclient: Client = Client(5384)
    if len(sys.argv) != 2:
        print("Usage: python client.py <port>")
        sys.exit(1)
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be an integer.")
        sys.exit(1)

    myclient: Client = Client(port)
