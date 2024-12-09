### Server Task Table

| **Server Task**          | **Description**                                                                  | **Communication Protocol**         | **Role**               |
|--------------------------|----------------------------------------------------------------------------------|-------------------------------------|------------------------|
| **UID Management**       | Generate and manage a unique identifier for the server                          | N/A                                 | All Server Nodes       |
| **Leader Election**      | Implement LCR algorithm for electing Idle Node Manager and Auctioneers          | Reliable Total Ordering Multicast   | INM and Auctioneer Nodes |
| **Dynamic Discovery**    | Discover and register new server nodes using UDP Broadcast                      | UDP Broadcast                       | All Server Nodes       |
| **Join System**          | Handle new servers joining the system and update group membership               | Reliable FIFO Multicast             | INM                    |
| **Start Auction**        | Initiate and manage a new auction assign Auctioneer and Followers               | Reliable FIFO Multicast             | INM                    |
| **Finalize Auction**     | Close an auction notify clients and reassign Auctioneer roles if needed         | Reliable Total Ordering Multicast   | Active Auctioneer      |
| **Heartbeat Mechanism**  | Send and receive periodic heartbeat messages to monitor node liveliness         | Reliable FIFO Multicast             | INM and Auctioneer Nodes |
| **Handle Failures**      | Detect node failures via missed heartbeats and trigger re-election if necessary | Reliable Total Ordering Multicast   | INM and Auctioneer Nodes |
| **Data Replication**     | Replicate auction data across follower nodes to ensure consistency and fault tolerance | Reliable FIFO Multicast         | Active Auctioneer      |
| **Maintain Ring Topology** | Manage the ring structure for communication and leader election                | Reliable FIFO Multicast             | INM                    |

---

### Client Task Table

| **Client Task**                   | **Description**                                         | **Communication Protocol**        |
|-----------------------------------|---------------------------------------------------------|------------------------------------|
| **UID Management**                | Generate and manage a unique identifier for the client  | N/A                                |
| **Command Line Interface CLI**    | Provide user interaction through CLI commands like list start join bid leave | N/A                                |
| **Request Available Items**       | Request a list of available auction items from INM      | Reliable FIFO Multicast             |
| **Start Auction**                 | Initiate a new auction for a specific item              | Reliable FIFO Multicast             |
| **Join Auction**                  | Join an existing auction managed by an Auctioneer       | Reliable FIFO Multicast             |
| **Leave Auction**                 | Leave an ongoing auction gracefully                     | Reliable Total Ordering Multicast   |
| **Place Bid**                     | Submit a bid to the active Auctioneer                   | Reliable Total Ordering Multicast   |
| **Handle Server Failures**        | Re discover and connect to a new Auctioneer if current one fails | Reliable FIFO Multicast         |
| **Rejoin Auction**                | Automatically rejoin an auction after transient disconnections | Reliable FIFO Multicast         |

---



# DS1 Project Proposal: Auction System

## Changes Based on Feedback

1. **What is "reliable fifo broadcast"?**
   -  reliable fifo multicast - udp https://stackoverflow.com/questions/107668/what-do-you-use-when-you-need-reliable-udp/

2. **The heartbeat protocol could be further clarified**
   - Heartbeat Frequency: Heartbeat messages are sent every 2 seconds.
   - Failure Detection: All nodes monitor heartbeats, and the first node to detect a failure initiates the LCR election.
   - Passive Auctioneer Heartbeats: Passive auctioneer nodes send heartbeat messages to the active auctioneer.

3. **However, consider other scenarios where a leader election might be necessary**
   - when a new server with a higher ID joins the system, trigger a re-election using the LCR algorithm to ensure the highest ID node becomes the leader
   - other scenarios?

4. **Could you clarify what you mean by "total order, reliable unicast"?**
   - Reliable total ordering multicast 

## Project Requirements
- Dynamic Discovery of Hosts
- Fault Tolerance
- Election
- Ordered Reliable Multicast

## Introduction
This proposal outlines a distributed auction system built using Python, focusing on real-time auction creation and bidding. The system will be developed without a GUI, and code management will be handled through GitHub.

## Project Requirements Analysis

### Architectural Description
The system uses a client-server model where auctioneer nodes manage bids, track the highest bid, and handle auction status, while bidder nodes represent participants. Critical auction data will be replicated across multiple servers to ensure fault tolerance, availability, and scalability.

We group the system components into the following groups:

- **Clients:** Clients can start, join, and leave an auction.
- **Idle Server Nodes:** Idle server nodes are nodes on the server side which don't have an active job. They wait until they have a new job assigned to them.
- **Idle Node Manager (INM):** The idle node manager is elected among the idle server nodes through LCR and manages them. It handles the joining of new server nodes and the starting of new auctions. We do not implement a distributed database and assume the INM has access to a concurrent, fault-tolerant, and scalable API which offers data on which auctioning items are available.
- **Auctioneer Nodes:** Auctioneer nodes are nodes currently assigned to handle a unique auction. Among the auctioneer nodes they elect a leader (active auctioneer node) through LCR to handle logic and communication with the clients currently participating in the auction. The non-leader nodes (follower/passive auctioneer nodes) represent passive nodes used for replication in case of failure of the leader. After election, the INM assigns three follower nodes to each auctioneer node.

### Dynamic Discovery of Hosts
All system components can join and leave without disrupting ongoing auctions.

- **Client requesting information on available items:** Broadcast to all servers, INM responds with a list of IDs.
- **Client starting an auction:** The client sends a reliable FIFO broadcast message to all server nodes. The INM then selects a set of idle nodes and assigns them as auctioneer nodes for the requested auction and removes the item from the auction list. The INM responds with the new IP address of the active auctioneer node to the client, who then uses reliable unicast for further communication.
- **Client joining an auction:** Broadcast to all server nodes, active auctioneer node with said ID responds. Further communication using total order unicast.
- **Client leaving:** Do nothing.
- **Server node joining:** A server sends a reliable FIFO broadcast message to all server nodes. The INM acknowledges the response. The new node joins the pool of idle server nodes.
- **Auction finished:** Active auctioneer node sends closing messages to participating clients. Active and passive auctioneer nodes join again as idle server nodes.
- **Server node leaving:** Server nodes don't leave. Crashing is handled in the "Fault Tolerance" section.

### Fault Tolerance
Liveliness of system components is checked through regular heartbeat messages.

- **Clients:** Do nothing.
- **Idle Server Nodes:** INM sends regular heartbeat messages to check liveliness. In case of failure, note it.
- **INM:** INM liveliness is checked through regular heartbeat messages by idle server nodes. In case of failure, use LCR among idle nodes to elect a new INM.
- **Active Auctioneer:** Liveliness is checked by passive auctioneer nodes using heartbeat messages. Use LCR among passive auctioneer nodes to elect a new leader. Update clients with the new IP address of the new leader and request a third follower from the INM. The data will be restored by majority vote over the followers' data. After election, the INM assigns three follower nodes to an auctioneer node. In case of failure of an auctioneer, the data will be restored by majority vote over the followers' data.
- **Passive Auctioneer:** Liveliness is checked by active auctioneer nodes using heartbeat messages. In case of failure, request a new passive auctioneer node from INM using a reliable broadcast message.

### Election
We use LCR in two different cases: To elect an INM and to elect an active auctioneer node within an ongoing auction.

### Communication
To ensure fairness for all clients in an auction, we use total order, reliable unicast for communication between clients and the active auctioneer node. For internal communication on the server side, reliable communication with FIFO ordering is sufficient.
