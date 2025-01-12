import json
import uuid
import threading
import select
import sys
from middleware import MessageType
from middleware import Message
from middleware.unicast import UnicastSocket
from middleware.multicast import MulticastSocket
from middleware import get_my_ip

class Client:
    def __init__(self, port: int) -> None:
        self.uuid: uuid.UUID = uuid.uuid4()
        self.ip: str = get_my_ip()
        self.port: int = port
        self.joined_auctions: dict[str, dict] = {}  # Store joined auctions

        self.unicast_soc: UnicastSocket = UnicastSocket(self.port)
        self.multicast_soc: MulticastSocket = MulticastSocket(self.port)
        self.inm_address: tuple[str, int] = ("", -1)  # (IP, port) of the INM - still used for responses, might be removed later
        # remove inm_unicast_soc and replace it by unicast_soc
        # self.inm_unicast_soc: UnicastSocket = None  # Socket for persistent INM connection
        self.listener_thread: threading.Thread = threading.Thread(target=self.listen_for_messages)
        self.listener_thread.daemon = True  # Allow the main thread to exit even if the listener thread is running
        self.listener_thread.start()
        self.main()

    def main(self):
        while True:
            self.cli()

    def cli(self):
        while True:
            # removed connect from input
            command = input("Enter command (info, list, start <item_id>, join <item_id>, bid <item_id> <amount>, exit): ")
            command_parts = command.split()

            if command_parts:
                action = command_parts[0]

                # removed connect case
                if action == "list":
                    self.list_items()
                    break
                if action == "info":  # Handle 'info' command
                    self.display_client_info()
                    break
                if action == "start":
                    if len(command_parts) == 2:
                        item_id = command_parts[1]
                        self.start_auction(item_id)
                    else:
                        print("Invalid start command. Usage: start <item_id>")
                    break
                if action == "join":
                    if len(command_parts) == 2:
                        item_id = command_parts[1]
                        self.join_auction(item_id)
                    else:
                        print("Invalid join command. Usage: join <item_id>")
                    break
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
                elif action == "exit":
                    print("Exiting client...")
                    exit()
                else:
                    print("Invalid command.")

    # removed connect_to_inm TODO: ADD CONNECT TO INM AND USE UNICAST?

    def listen_for_messages(self):
        while True:
            # Listen on self.unicast_soc
            sockets_to_listen = [self.unicast_soc]

            ready, _, _ = select.select(sockets_to_listen, [], [], 1)
            for sock in ready:
                response: Message = sock.receive()
                if response is not None:
                    if response.message_type == MessageType.LIST_ITEMS_RESPONSE:
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
                    elif response.message_type == MessageType.START_AUCTION_RESPONSE:
                        if response.content.startswith("ERROR"):
                            print(f"Failed to start auction: {response.content}")
                        else:
                            aan_ip, aan_port = response.content.split(",")
                            self.aan_address = (aan_ip, int(aan_port))
                            print(f"Auction started. AAN address: {aan_ip}:{aan_port}")
                    elif response.message_type == MessageType.JOIN_AUCTION_RESPONSE:
                        if response.content == "failed":
                            print(f"Failed to join auction")
                        else:
                            item_id, highest_bid, highest_bidder = response.content.split(
                                ","
                            )
                            self.aan_address = (
                                response.src_ip,
                                response.src_port,
                            )  # Store AAN address
                            # Update joined_auctions
                            self.joined_auctions[item_id] = {
                                "highest_bid": highest_bid,
                                "highest_bidder": highest_bidder,
                            }
                            print(f"Successfully joined auction for item {item_id}")
                            print(
                                f"  Current highest bid: {highest_bid} (by {highest_bidder if highest_bidder != 'None' else 'no one'})"
                                )
                    elif response.message_type == MessageType.BID_RESPONSE: # this handling is terrible but no other way because of message format
                        print(f"Bid response: {response.content}")
                        if response.content.startswith("Bid-for"):
                            parts = response.content.split("-")
                            if len(parts) == 7:  # Bid accepted (Corrected length check)
                                item_id = parts[2]
                                bid_amount = parts[6]

                                # Update joined_auctions with new bid information
                                if item_id in self.joined_auctions:
                                    self.joined_auctions[item_id]["highest_bid"] = bid_amount
                                    self.joined_auctions[item_id]["highest_bidder"] = str(self.uuid)
                                    print(
                                        f"Bid for {item_id} accepted. New highest bid: {bid_amount} by you"
                                    )
                            elif len(parts) == 11:  # Bid rejected (Corrected length check)
                                item_id = parts[2]
                                bid_amount = parts[4]
                                highest_bid = parts[10]
                                # Update joined_auctions with new bid information
                                self.joined_auctions[item_id]["highest_bid"] = highest_bid
                                self.joined_auctions[item_id]["highest_bidder"] = "another client"
                                print(
                                        f"Bid for {item_id} for {bid_amount} rejected. Current highest bid: {highest_bid} by another client"
                                    )
                    else:
                        print(
                            f"Received unknown or invalid message: {response}"
                        )

    def display_client_info(self) -> None:
        """Displays the client's current information."""
        print("\n===== Client Info =====")
        print(f"UUID: {self.uuid}")
        print(f"IP: {self.ip}")
        print(f"Port: {self.port}")

        # Check if AAN address is available and display it
        if hasattr(self, 'aan_address') and self.aan_address[1] != -1:
            print(f"AAN Address: {self.aan_address[0]}:{self.aan_address[1]}")
        else:
            print("AAN Address: None")

        if self.joined_auctions:
            print("Joined Auctions:")
            for item_id, auction_data in self.joined_auctions.items():
                print(f"    Item ID: {item_id}")
                print(f"    Highest Bid: {auction_data['highest_bid']}")
                print(f"    Highest Bidder: {auction_data['highest_bidder']}")
        else:
            print("Joined Auctions: None")

        print("=======================\n")

    def list_items(self):
        # broadcast the request to all servers
        self.multicast_soc.send(MessageType.LIST_ITEMS_REQUEST, str(self.uuid))
        print("Sent LIST_ITEMS_REQUEST to INM")

    def start_auction(self, item_id: str = ""):
        # broadcast the request to all servers
        self.multicast_soc.send(MessageType.START_AUCTION_REQUEST, item_id)
        print(f"Sent START_AUCTION_REQUEST for item {item_id} to INM")

    def join_auction(self, item_id: str):
        """
        Sends a JOIN_AUCTION_REQUEST to the AAN.
        """
        message_content = f"{item_id},{self.uuid}"
        self.multicast_soc.send(MessageType.JOIN_AUCTION_REQUEST, message_content)  # Use multicast
        # #self.unicast_soc.send(MessageType.JOIN_AUCTION_REQUEST, message_content, self.aan_address[0], self.aan_address[1])
        print(f"Sent JOIN_AUCTION_REQUEST for item {item_id} to AAN")

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
