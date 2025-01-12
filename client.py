import json
import uuid
import threading
import select
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
            command = input("Enter command (list, start, join, bid, exit): ")
            command_parts = command.split()

            if command_parts:
                action = command_parts[0]

                # removed connect case
                if action == "list":
                    self.list_items()
                # ... (other actions)
                if action == "start":
                    item_id = input("Enter item ID to start auction: ")
                    self.start_auction(item_id)
                elif action == "exit":
                    print("Exiting client...")
                    exit()
                else:
                    print("Invalid command.")

    # removed connect_to_inm TODO: ADD CONNECT TO INM AND USE UNICAST?

    def list_items(self):
        # broadcast the request to all servers
        self.multicast_soc.send(MessageType.LIST_ITEMS_REQUEST, str(self.uuid))
        print("Sent LIST_ITEMS_REQUEST to INM")

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
                    else:
                        print(
                            f"Received unknown or invalid message: {response}"
                        )



    def start_auction(self, item_id: str = ""):
        # broadcast the request to all servers
        self.multicast_soc.send(MessageType.START_AUCTION_REQUEST, item_id)
        print(f"Sent START_AUCTION_REQUEST for item {item_id} to INM")

if __name__ == "__main__":
    myclient: Client = Client(5384)