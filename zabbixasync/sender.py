import json
import logging
import struct
from typing import Any


logger = logging.getLogger(__name__)


class AsyncSender():
    __slots__ = ("server", "port")

    def __init__(self, server: str, port: int = 10051) -> None:
        self.server = server
        self.port = port

    def send(self, host: str, key: str, value: Any):

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
        packet = b'ZBXD' + b'\x01' + payload_len + b'\x00\x00\x00\x00' + payload_bytes
        
        print(packet)
