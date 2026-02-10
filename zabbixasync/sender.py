from dataclasses import dataclass
import json
import logging
import re
import struct
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple
import asyncio
import ssl
import zlib


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
    __slots__ = [
        "server",
        "port",
        "timeout",
        "tls_connect",
        "tls_psk_identity",
        "tls_psk",
        "tls_psk_file",
        "tls_server_name",
    ]
    HEADER_SIZE = 13
    BUFFER_SIZE = 1024

    def __init__(
            self,
            server: str,
            port: int = 10051,
            timeout: Optional[float] = None,
            tls_connect: Optional[str] = None,
            tls_psk_identity: Optional[str] = None,
            tls_psk: Optional[str] = None,
            tls_psk_file: Optional[str] = None,
            tls_server_name: Optional[str] = None) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout
        self.tls_connect = tls_connect
        self.tls_psk_identity = tls_psk_identity
        self.tls_psk = tls_psk
        self.tls_psk_file = tls_psk_file
        self.tls_server_name = tls_server_name

        self._validate_tls_options()

    def _validate_tls_options(self) -> None:
        if self.tls_connect is None:
            return

        if self.tls_connect != 'psk':
            raise ValueError("only tls_connect='psk' is supported")

        if not self.tls_psk_identity:
            raise ValueError('tls_psk_identity is required for PSK')

        if bool(self.tls_psk) == bool(self.tls_psk_file):
            raise ValueError(
                'set exactly one of tls_psk or tls_psk_file for PSK')

    def _create_payload(self, items: Sequence[ItemData]) -> bytes:
        payload = json.dumps({
            "request": "sender data",
            "data": items
        }).encode('utf-8')

        return payload

    def _create_packet(self, items: Sequence[ItemData]) -> bytes:
        # https://www.zabbix.com/documentation/current/en/manual/appendix/items/trapper
        payload = self._create_payload(items)
        packet = b'ZBXD' + b'\x01' + struct.pack('<II', len(payload), 0) + payload

        logging.debug(f'packet created, length: {len(packet)} bytes')
        return packet

    def _parse_response_header(self, header: bytes) -> Tuple[int, bool]:
        if len(header) != self.HEADER_SIZE:
            raise ValueError('invalid zabbix header size')

        if header[0:4] != b'ZBXD':
            raise ValueError('zabbix header not found or incorrect')

        flags = header[4]
        if not flags & 0x01:
            raise ValueError('invalid zabbix protocol version flag')

        # Zabbix header in 7.0 still uses 13 bytes:
        # magic(4) + flags(1) + datalen(4) + reserved(4)
        # For normal packets (flag 0x04 not set), reserved is 0.
        # For large packets (flag 0x04 set), datalen is 64-bit using both fields.
        data_len_low, data_len_high = struct.unpack('<II', header[5:])
        response_size = data_len_low + (data_len_high << 32)
        compressed = bool(flags & 0x02)

        logging.debug('response header received, response size %d bytes', response_size)
        if compressed:
            logging.debug('response payload is compressed')

        return response_size, compressed

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
        header = await reader.readexactly(self.HEADER_SIZE)
        resp_size, compressed = self._parse_response_header(header)

        data = b''
        while len(data) < resp_size:
            buffer = await reader.read(min(self.BUFFER_SIZE, resp_size - len(data)))
            if not buffer:
                raise ConnectionError('connection closed before full response was received')
            data += buffer

        if compressed:
            data = zlib.decompress(data)

        resp = self._parse_response(data)
        return resp

    def _parse_psk(self) -> bytes:
        if self.tls_psk_file:
            raw = Path(self.tls_psk_file).read_text(encoding='utf-8').strip()
        else:
            raw = str(self.tls_psk).strip()

        if not raw:
            raise ValueError('PSK cannot be empty')

        try:
            return bytes.fromhex(raw)
        except ValueError as exc:
            raise ValueError('PSK must be a valid hex string') from exc

    def _create_psk_ssl_context(self) -> ssl.SSLContext:
        psk = self._parse_psk()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('PSK')

        if hasattr(context, 'set_psk_client_callback'):
            # Python 3.13+ OpenSSL callback API.
            context.set_psk_client_callback(lambda _hint: (self.tls_psk_identity, psk))
            return context

        try:
            from sslpsk3 import SSLPSKContext  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError(
                "TLS-PSK requires Python 3.13+ or package 'sslpsk3'"
            ) from exc

        compat_context = SSLPSKContext(ssl.PROTOCOL_TLS)
        compat_context.check_hostname = False
        compat_context.verify_mode = ssl.CERT_NONE
        compat_context.set_ciphers('PSK')
        compat_context.psk = psk
        compat_context.psk_identity = self.tls_psk_identity.encode('utf-8')
        return compat_context

    def _get_connection_kwargs(self) -> dict:
        kwargs = {}

        if self.timeout is not None:
            kwargs['ssl_handshake_timeout'] = self.timeout

        if self.tls_connect == 'psk':
            kwargs['ssl'] = self._create_psk_ssl_context()
            kwargs['server_hostname'] = self.tls_server_name or self.server

        return kwargs

    async def send(self, items=None) -> ZabbixResponse:
        # force items to an array
        if isinstance(items, ItemData):
            items = [items]

        if items is None:
            items = []

        logging.debug(
            f'sending {len(items)} metrics to {self.server}:{self.port}')

        packet = self._create_packet(items)

        reader, writer = await asyncio.open_connection(
            self.server,
            self.port,
            **self._get_connection_kwargs())
        await self._write_data(writer, packet)

        response = await self._read_response(reader)

        writer.close()
        await writer.wait_closed()

        return response
