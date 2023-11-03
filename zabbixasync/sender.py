import json
import logging
import struct
from typing import Any
import asyncio


logger = logging.getLogger(__name__)

class ZabbixMetric(object):
    __slots__ = ("host", "key", "value")

    def __init__(self, host : str, key : str, value : Any, clock=None):
        self.host = str(host)
        self.key = str(key)
        self.value = str(value)

class AsyncSender():
    __slots__ = ("server", "port")
    HEADER_SIZE = 13
    BUFFER_SIZE = 1024

    def __init__(self, server: str, port: int = 10051) -> None:
        self.server = server
        self.port = port   

    async def send(self, host: str, key: str, value: Any):

        request_payload = json.dumps({
            "request": "sender data",
            "data": [{
                "host": host,
                "key": key,
                "value": str(value)
            }]
        })

        payload_bytes = request_payload.encode('utf-8')
        payload_len = struct.pack('<L', len(payload_bytes))
        zabbix_packet = b'ZBXD' + b'\x01' + payload_len + b'\x00\x00\x00\x00' + payload_bytes
        print(f'sending: {zabbix_packet}')
        reader, writer = await asyncio.open_connection(self.server, self.port)
        writer.write(zabbix_packet)
        await writer.drain()
        
        header = await reader.read(self.HEADER_SIZE)
        #example of received header: b'ZBXD\x01Z\x00\x00\x00\x00\x00\x00\x00'
        print(f'Received Header: {header}')
        _, _, resp_size = struct.unpack('<4s1sQ', header)
        
        #example of received data: b'{"response":"success","info":"processed: 1; failed: 0; total: 1; seconds spent: 0.000051"}'
        data = b''
        buffer = b''
        while len(data) < resp_size:
            buffer = await reader.read(self.BUFFER_SIZE)
            print(f'buffer : {buffer}')
            data += buffer


        return
