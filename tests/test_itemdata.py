import json
from unittest import TestCase

from zabbixasync.sender import ItemData

class TestItemData(TestCase):
    def test_init(self):
        expected = '{"host": "localhost", "key": "test", "value": 123456}'
        id = ItemData('localhost', 'test', 123456)
        dump = json.dumps(id)
        self.assertEqual(dump, expected)

    def test_init_with_ns_clock(self):
        expected = '{"host": "localhost", "key": "test", "value": 123456, "clock": 123456789, "ns": 123456789}'
        id = ItemData('localhost', 'test', 123456, 123456789, 123456789)
        dump = json.dumps(id)
        self.assertEqual(dump, expected)