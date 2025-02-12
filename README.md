# Readme
This project is part of the course `Distributed Systems 1` at the University of Stuttgart in the Winter term of 24/25. We implement a distributed auctioning system with focus on robustness towards node crashes and network packet loss.  
The written report can be found [here](/group18_AuctionSystem_Report.pdf).  

# Quick-Start
Our core components are the server nodes and clients. Most of the networking functionality is abstracted in a shared middleware. Further details are in the written report.  
Servers can be started as `python server.py <port> [<uuid>]` and clients can be started as `python client.py <port>`.