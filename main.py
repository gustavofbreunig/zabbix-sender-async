import asyncio
from zabbixasync.sender import AsyncSender

async def main():
    sender = AsyncSender("localhost", 10051)
    await sender.send('localhost', 'teste.string', "odfijgosifjdfis")


if __name__ == "__main__":
    asyncio.run(main())