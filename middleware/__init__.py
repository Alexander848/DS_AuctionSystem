

# implements communication
# ack
# heartbeat
# detect failures


from enum import Enum
import socket


class MessageType(Enum):
    TEST = "TEST"                       # test message
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"         # unicast to send UUID
    ELECTION_START = "ELECTION_START"   # starts an election. election message.
    ELECTION_ACK = "ELECTION_ACK"       # acknowledges. ok/alive message.
    DECLARE_INM = "DECLARE_INM"         # declares the sender to be the INM. coordination message.
    INM_ANSWER = "INM_ANSWER"           # INM response to get INM address
    UNICAST_ACK = "UNICAST_ACK"         # ack for unicast message


class Message():
    def __init__(self, message_type: MessageType = MessageType.TEST, content: str = "", src_ip: str = "-1", src_port: int = -1, message_id: int = -1) -> None:
        self.message_type : MessageType = message_type
        self.content: str = content
        self.src_ip: str = src_ip
        self.src_port: int = src_port
        self.message_id: int = message_id

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



















