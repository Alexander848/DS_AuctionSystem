import time
import os, sys
from threading import Thread
import multiprocessing

import server
from middleware import Message
from middleware import MessageType
from middleware import get_my_ip
from middleware.unicast import UnicastSocket
from middleware.multicast import MulticastSocket

''' Disable print outs -> HiddenPrints():
class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout'''


# Scenario 1: Multiple Servers Start Simultaneously
# TODO Add control mechanisms -> result_dict[0] = False
def test_scenario_1(result_dict) -> None:
    server1: server.Server = server.Server(5101, 11)
    server2: server.Server = server.Server(5102, 12)
    server3: server.Server = server.Server(5103, 13)
    server5: server.Server = server.Server(5105, 15)
    server4: server.Server = server.Server(5104, 14)
    time.sleep(5)
    server1.stop_execution = True
    server2.stop_execution = True
    server3.stop_execution = True
    server4.stop_execution = True
    server5.stop_execution = True

    result_dict[0] = True


# Scenario 2: Servers Start Sequentially (in this case 5 second intervals)
# TODO Add control mechanisms -> result_dict[1] = False
def test_scenario_2(result_dict) -> None:
    server1 : server.Server = server.Server(5201, 21)
    time.sleep(2)
    server2 : server.Server = server.Server(5202, 22)
    time.sleep(2)
    server1.stop_execution = True
    server3: server.Server = server.Server(5203, 23)
    time.sleep(2)
    server2.stop_execution = True
    server5: server.Server = server.Server(5205, 25)
    time.sleep(2)
    server4: server.Server = server.Server(5204, 24)
    time.sleep(2)
    server5.stop_execution = True
    time.sleep(1)
    server4.stop_execution = True
    server3.stop_execution = True

    result_dict[1] = True


if __name__ == "__main__":
    mgr = multiprocessing.Manager()
    results = mgr.dict()
    test_scenario_1(results)

    '''
    results = mgr.dict()
    threadScenario2 = Thread(target=test_scenario_2, args=(results,))
    threadScenario2.start()
    threadScenario2.join()

    for i in range(10):
        if i in results and results[i] == True:
            print("Test Scenario {}: Successful".format(i))
        else:
            print("Test Scenario {}: Failed".format(i))'''

    '''server = server.Server(5101, 11)
    time.sleep(4)
    print("GO!")
    server.stop_execution = True'''