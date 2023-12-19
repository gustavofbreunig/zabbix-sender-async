from dataclasses import dataclass
import json
import logging
import re
import struct
from typing import Any, Optional
import asyncio


logger = logging.getLogger(__name__)
ZABBIX_RETURN_REGEX = re.compile(
    r'processed: (\d+); failed: (\d+); total: (\d+); seconds spent: (\d+\.\d+)'
    )


class ItemData(dict):
    """
    Dictionary representing a trapper item.
    """
    __slots__ = ['__dict__']

    # implementing a dictionary helps to json.dumps
    def __init__(self,
                 host: str,
                 key: str,
                 value: Any,
                 clock: Optional[int] = None,
                 ns: Optional[int] = None):
        dict.__init__(self, host=host, key=key, value=value)
        if clock is not None:
            self['clock'] = clock
        if ns is not None:
            self['ns'] = ns


@dataclass
class ZabbixResponse:
    processed: int
    failed: int
    total: int
    seconds_spent: float
    response: str


class AsyncSender():
    __slots__ = ["server", "port"]
    HEADER_SIZE = 13
    BUFFER_SIZE = 1024

    def __init__(self, server: str, port: int = 10051) -> None:
        self.server = server
        self.port = port

    def _create_payload(self, items):
        payload = json.dumps({
            "request": "sender data",
            "data": items
        }).encode('utf-8')

        return payload

    def _create_packet(self, items) -> bytes:
        # https://www.zabbix.com/documentation/current/en/manual/appendix/items/trapper
        payload = self._create_payload(items)
        payload_len = struct.pack('<L', len(payload))
        packet = b'ZBXD' + \
                 b'\x01' + \
                 payload_len + \
                 b'\x00\x00\x00\x00' + \
                 payload

        logging.debug(f'packet created, length: {len(packet)} bytes')
        return packet

    def _parse_response_header(self, header: bytes) -> int:
        if header[0:4] != b'ZBXD' or header[4] != 1:
            raise ValueError('zabbix header not found or incorrect')

        # discard first 5 bytes, the ZBXD + 1 useless byte
        response_size = struct.unpack('<Q', header[5:])

        logging.debug(
            f'response header received, response size {response_size[0]}bytes')

        return response_size[0]

    async def _write_data(self, writer: asyncio.StreamWriter, packet: bytes):
        writer.write(packet)
        await writer.drain()

    def _parse_response(self, response: bytes) -> ZabbixResponse:
        obj = json.loads(response)

        parsed_data = ZABBIX_RETURN_REGEX.match(obj['info'])

        response_object = ZabbixResponse(
            response=obj['response'],
            processed=int(parsed_data.group(1)),
            failed=int(parsed_data.group(2)),
            total=int(parsed_data.group(3)),
            seconds_spent=float(parsed_data.group(4))
        )
        logging.debug(f'parsed response: {response_object}')
        return response_object

    async def _read_response(self, reader: asyncio.StreamReader):
        header = await reader.read(self.HEADER_SIZE)
        resp_size = self._parse_response_header(header)

        data = b''
        buffer = b''
        while len(data) < resp_size:
            buffer = await reader.read(self.BUFFER_SIZE)
            data += buffer

        resp = self._parse_response(data)
        return resp

    async def send(self, items = None) -> ZabbixResponse:
        # force items to an array
        if type(items) is ItemData:
            items = [items]

        logging.debug(
            f'sending {len(items)} metrics to {self.server}:{self.port}')

        packet = self._create_packet(items)

        reader, writer = await asyncio.open_connection(self.server, self.port)
        await self._write_data(writer, packet)

        # return await self._read_response(reader)

        response = await self._read_response(reader)

        writer.close()
        await writer.wait_closed()

        return response
