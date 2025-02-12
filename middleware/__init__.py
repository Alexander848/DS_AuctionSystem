# implements communication
# ack
# heartbeat
# detect failures

from enum import Enum
import socket
from uuid import UUID


class MessageType(Enum):

    TEST = "TEST"                       # test message
    STOP_EXECUTION = "STOP_EXECUTION" # used to stop receive and delivery threads
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"           # unicast to send UUID
    ELECTION_START = "ELECTION_START"   # starts an election. election message.
    ELECTION_ACK = "ELECTION_ACK"       # acknowledges. ok/alive message.
    DECLARE_INM = "DECLARE_INM"         # declares the sender to be the INM. coordination message.
    DECLARE_INM_ACK = "DECLARE_INM_ACK" # acknowledges the DECLARE_INM message.
    INM_ANSWER = "INM_ANSWER"           # INM response to get INM address
    LIST_ITEMS_REQUEST = "LIST_ITEMS_REQUEST"
    LIST_ITEMS_RESPONSE = "LIST_ITEMS_RESPONSE"
    CONNECT_REQUEST = "CONNECT_REQUEST"
    CONNECT_RESPONSE = "CONNECT_RESPONSE"
    START_AUCTION_REQUEST = "START_AUCTION_REQUEST"
    START_AUCTION_RESPONSE = "START_AUCTION_RESPONSE"
    AUCTION_INIT = "AUCTION_INIT"
    PAN_REQUEST = "PAN_REQUEST"
    PAN_RESPONSE = "PAN_RESPONSE"
    STATE_QUERY = "STATE_QUERY"
    STATE_RESPONSE = "STATE_RESPONSE"
    PAN_FAILURE = "PAN_FAILURE"
    JOIN_AUCTION_REQUEST = "JOIN_AUCTION_REQUEST"
    JOIN_AUCTION_RESPONSE = "JOIN_AUCTION_RESPONSE"
    REPLICATE_STATE = "REPLICATE_STATE"
    BID_REQUEST = "BID_REQUEST"
    BID_RESPONSE = "BID_RESPONSE"
    PAN_INFO = "PAN_INFO"
    LIST_ITEMS_FROM_AAN_REQUEST = "LIST_ITEMS_FROM_AAN_REQUEST"
    AUCTION_END = "AUCTION_END"
    HEARTBEAT_REQUEST = "HEARTBEAT_REQUEST"
    HEARTBEAT_RESPONSE = "HEARTBEAT_RESPONSE"
    REMOVE_NODE = "REMOVE_NODE"
    GROUPVIEW_UPDATE = "GROUPVIEW_UPDATE"  # New message type for groupview updates
    GROUPVIEW_ACK = "GROUPVIEW_ACK"        # ack for groupview multicast
    REPLICATE_STATE_REQUEST = "REPLICATE_STATE_REQUEST"
    UNICAST_ACK = "UNICAST_ACK"         # ack for unicast message


class Message():
    def __init__(self, message_type: MessageType, content: str, src_ip: str, src_port: int, message_id: UUID) -> None:
        self.message_type : MessageType = message_type
        self.content: str = content
        self.src_ip: str = src_ip
        self.src_port: int = src_port
        self.message_id: UUID = message_id

    def __str__(self) -> str:
        return f"{self.message_type.value} {self.content} {self.src_ip} {self.src_port} {self.message_id}"



cached_ip: str = ""
def get_my_ip() -> str:
    global cached_ip
    if cached_ip == "":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        cached_ip = s.getsockname()[0]
        s.close()
    return cached_ip
