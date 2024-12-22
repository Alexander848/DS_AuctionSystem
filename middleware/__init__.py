

# implements communication
# ack
# heartbeat
# detect failures


from enum import Enum


class MessageType(Enum):
    TEST = "TEST"                       # test message
    UUID_QUERY = "UUID_QUERY"           # unicast to send UUID
    UUID_ANSWER = "UUID_ANSWER"         # unicast to send UUID
    INM_ANSWER = "INM_ANSWER"           # INM response to get INM address


class Message():
    def __init__(self, message_type: MessageType = MessageType.TEST, content: str = "", src_ip: str = "-1", src_port: int = -1) -> None:
        self.message_type : MessageType = message_type
        self.content: str = content
        self.src_ip: str = src_ip
        self.src_port: int = src_port

    def __str__(self) -> str:
        return f"{self.message_type.value} {self.content} {self.src_ip} {self.src_port}"


def get_my_ip() -> str:
    # defaults to 127.0.0.1 for me. workaround: hardcode IP
    #return socket.gethostbyname(socket.gethostname())
    return "192.168.2.103"     # override IP



















