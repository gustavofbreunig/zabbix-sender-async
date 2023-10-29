from zabbixasync.sender import AsyncSender


if __name__ == "__main__":
    sender = AsyncSender("localhost", 10051)
    sender.send('localhost', 'teste', 'fkkkkkkkkdkkkkkkkfdfdf')