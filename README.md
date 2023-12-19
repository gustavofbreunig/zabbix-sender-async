Zabbix Async Sender module for Python
========================

Install
-------

    pip install zabbix-sender-async


Examples
--------

import asyncio
from src.sender import AsyncSender, ItemData

async def sendmetrics():
    sender = AsyncSender('localhost', 10051)
    metric = ItemData(host='async-sender-test-host', key='test.metric.text', value='test package import')
    result = await sender.send(metric)
    print(result)

asyncio.run(sendmetrics())


Expected result:

