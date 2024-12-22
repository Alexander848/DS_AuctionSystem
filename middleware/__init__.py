

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


def get_my_ip() -> str:
    # defaults to 127.0.0.1 for me. workaround: hardcode IP
    #return socket.gethostbyname(socket.gethostname())
    return "192.168.2.103"     # override IP



















