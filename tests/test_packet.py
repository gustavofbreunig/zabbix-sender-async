from unittest import TestCase

from zabbixasync.sender import AsyncSender, ItemData

class TestPacket(TestCase):
    def test_packet_creation(self):
        expected = b'ZBXD\x01[\x00\x00\x00\x00\x00\x00\x00{"request": "sender data", "data": [{"host": "localhost", "key": "test", "value": 123456}]}'

        data = ItemData('localhost', 'test', 123456)
        items = [ data ]
        sender = AsyncSender('server')
        packet = sender._create_packet(items)

        self.assertEqual(packet, expected)