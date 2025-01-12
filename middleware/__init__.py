# implements communication
# ack
# heartbeat
# detect failures

from enum import Enum

class MessageType(Enum):

    TEST = "TEST"                       # test message
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"           # unicast to send UUID
    ELECTION_START = "ELECTION_START"   # starts an election. election message.
    ELECTION_ACK = "ELECTION_ACK"       # acknowledges. ok/alive message.
    DECLARE_INM = "DECLARE_INM"         # declares the sender to be the INM. coordination message.
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
class Message():
    def __init__(self, message_type: MessageType = MessageType.TEST, content: str = "", src_ip: str = "-1", src_port: int = -1) -> None:
        print("[middleware/init.py] [Message.__init__]")
        self.message_type : MessageType = message_type
        self.content: str = content
        self.src_ip: str = src_ip
        self.src_port: int = src_port

    def __str__(self) -> str:
        print(f"  [middleware/init.py] [Message.__str__] {self.message_type.value} {self.content} {self.src_ip} {self.src_port}")
        return f"{self.message_type.value} {self.content} {self.src_ip} {self.src_port}"

def get_my_ip() -> str:
    # defaults to 127.0.0.1 for me. workaround: hardcode IP
    #return socket.gethostbyname(socket.gethostname())
    return "172.22.51.255"     # override IP