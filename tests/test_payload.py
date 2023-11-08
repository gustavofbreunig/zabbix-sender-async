from unittest import TestCase

from zabbixasync.sender import AsyncSender, ItemData

class TestPayload(TestCase):
    def test_payload_content(self):
        expected = b'{"request": "sender data", "data": [{"host": "localhost", "key": "test", "value": 123456}]}'

        data = ItemData('localhost', 'test', 123456)
        items = [ data ]
        sender = AsyncSender('server')
        payload = sender._create_payload(items)

        self.assertEqual(payload, expected)

        