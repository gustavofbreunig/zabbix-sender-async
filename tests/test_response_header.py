from unittest import TestCase

from zabbixasync.sender import AsyncSender

class TestResponseHeader(TestCase):
    def setUp(self):
        self.sender = AsyncSender('server')  

    def test_packet_creation(self):
        header_received = b'ZBXD\x01[\x00\x00\x00\x00\x00\x00\x00'
        expected = 91
        res = self.sender._parse_response_header(header_received)

        self.assertEqual(res, expected)

    def test_packet_header_incorrect(self):
        with self.assertRaises(ValueError) as context:
            header_received_incorrect = b'EEEE\x01[\x00\x00\x00\x00\x00\x00\x00'
            self.sender._parse_response_header(header_received_incorrect)

    def test_packet_header_slightly_incorrect(self):
        with self.assertRaises(ValueError) as context:
            header_received_incorrect = b'ZBXD\x03[\x00\x00\x00\x00\x00\x00\x00'
            self.sender._parse_response_header(header_received_incorrect)            