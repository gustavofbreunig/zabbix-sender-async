!(https://github.com/gustavofbreunig/zabbix-sender-async/actions/workflows/python-app.yml/badge.svg)

Zabbix Async Sender module for Python
========================

Install
-------

    pip install zabbix-sender-async


Examples
--------

```python
import asyncio
from zabbixasync.sender import AsyncSender, ItemData

async def sendmetrics():
    sender = AsyncSender('localhost', 10051)
    metric = ItemData(host='hostname', key='test.metric.text', value='test package import')
    result = await sender.send(metric)
    print(result)

asyncio.run(sendmetrics())
```

Expected result:

```
ZabbixResponse(processed=1, failed=0, total=1, seconds_spent=0.00019, response='success')
```