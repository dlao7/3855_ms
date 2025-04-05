### Remaining

* Kafka can now reconnect using the same broker ID so the leader election works
* Stopping and restarting Kafka causes consumers to not consume messages
  * analyzer - incorrect counts
  * storage - does not consume messages to enter into mySQL database
* Receiver appears to work? Kafka queue has all messages (even the stopped ones)

### Folder Structure for Uncreated Folders: ###

```
├── data
│   ├── check
│   ├── database
│   ├── kafka
│   └── processing
├── logs
│   ├── analyzer
│   ├── check
│   ├── processing
│   ├── receiver
│   └── storage
```

### Ports ###
* receiver: 8080
* processing: 8100
* analyzer: 8200
* consistency_check: 8300
