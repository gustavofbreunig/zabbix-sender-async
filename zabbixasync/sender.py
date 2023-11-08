import json
import logging
import struct
from typing import Any, Optional
import asyncio


logger = logging.getLogger(__name__)

class ItemData(dict):
    """
    Dictionary representing a trapper item.
    """
    __slots__ = ['__dict__']

    #implementing a dictionary helps to json.dumps
    def __init__(self, host: str, key: str, value: Any, clock: Optional[int] = None, ns: Optional[int] = None):
        dict.__init__(self, host=host, key=key, value=value)
        if clock != None:
            self['clock'] = clock
        if ns != None:
            self['ns'] = ns


class AsyncSender():
    __slots__ = ["server", "port"]
    HEADER_SIZE = 13
    BUFFER_SIZE = 1024

    def __init__(self, server: str, port: int = 10051) -> None:
        self.server = server
        self.port = port   

    def _create_payload(self, items : list[ItemData]):
        payload = json.dumps({
            "request": "sender data",
            "data": items
        }).encode('utf-8')

        logging.debug(f'Payload created, {len(payload)} bytes: {payload}')
        return payload
    
    def _create_packet(self, items : list[ItemData]):
        #https://www.zabbix.com/documentation/current/en/manual/appendix/items/trapper
        payload = self._create_payload(items)
        payload_len = struct.pack('<L', len(payload))
        packet = b'ZBXD' + b'\x01' + payload_len + b'\x00\x00\x00\x00' + payload

        logging.debug(f'Zabbix packet created, {len(packet)} bytes: {packet}')
        return packet

    async def send(self, items : list[ItemData]):
        packet = self._create_packet(items)

        reader, writer = await asyncio.open_connection(self.server, self.port)
        writer.write(packet)
        await writer.drain()
        
        header = await reader.read(self.HEADER_SIZE)
        #example of received header: b'ZBXD\x01Z\x00\x00\x00\x00\x00\x00\x00'
        _, _, resp_size = struct.unpack('<4s1sQ', header)
        
        #example of received data: b'{"response":"success","info":"processed: 1; failed: 0; total: 1; seconds spent: 0.000051"}'
        data = b''
        buffer = b''
        while len(data) < resp_size:
            buffer = await reader.read(self.BUFFER_SIZE)
            data += buffer
        
        writer.close()
        await writer.wait_closed()