from unittest import TestCase

from zabbixasync.sender import AsyncSender


class TestResponseHeader(TestCase):
    def setUp(self):
        self.sender = AsyncSender('server')

    def test_packet_creation(self):
        header_received = b'ZBXD\x01[\x00\x00\x00\x00\x00\x00\x00'
        expected = 91
        res, compressed = self.sender._parse_response_header(header_received)

        self.assertEqual(res, expected)
        self.assertFalse(compressed)

    def test_packet_creation_compressed(self):
        header_received = b'ZBXD\x03[\x00\x00\x00\x00\x00\x00\x00'
        expected = 91
        res, compressed = self.sender._parse_response_header(header_received)

        self.assertEqual(res, expected)
        self.assertTrue(compressed)

    def test_packet_header_incorrect(self):
        with self.assertRaises(ValueError):
            header_received_incorrect = \
                b'EEEE\x01[\x00\x00\x00\x00\x00\x00\x00'
            self.sender._parse_response_header(header_received_incorrect)

    def test_packet_header_slightly_incorrect(self):
        with self.assertRaises(ValueError):
            header_received_incorrect = \
                b'ZBXD\x00[\x00\x00\x00\x00\x00\x00\x00'
            self.sender._parse_response_header(header_received_incorrect)
