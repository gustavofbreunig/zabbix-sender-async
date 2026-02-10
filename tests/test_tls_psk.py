import os
from tempfile import NamedTemporaryFile
from unittest import TestCase

from zabbixasync.sender import AsyncSender


class TestTlsPsk(TestCase):
    def test_validate_requires_identity(self):
        with self.assertRaises(ValueError):
            AsyncSender(
                "server",
                tls_connect="psk",
                tls_psk="1A2B",
            )

    def test_validate_requires_single_psk_source(self):
        with self.assertRaises(ValueError):
            AsyncSender(
                "server",
                tls_connect="psk",
                tls_psk_identity="id",
            )

        with self.assertRaises(ValueError):
            AsyncSender(
                "server",
                tls_connect="psk",
                tls_psk_identity="id",
                tls_psk="1A2B",
                tls_psk_file="dummy",
            )

    def test_parse_psk_from_string(self):
        sender = AsyncSender(
            "server",
            tls_connect="psk",
            tls_psk_identity="id",
            tls_psk="00112233445566778899AABBCCDDEEFF",
        )

        self.assertEqual(
            sender._parse_psk(),
            bytes.fromhex("00112233445566778899AABBCCDDEEFF"),
        )

    def test_parse_psk_from_file(self):
        with NamedTemporaryFile(
                mode="w+",
                encoding="utf-8",
                delete=False) as temp:
            temp.write("00112233445566778899AABBCCDDEEFF\n")
            temp.flush()
            temp_name = temp.name

        try:
            sender = AsyncSender(
                "server",
                tls_connect="psk",
                tls_psk_identity="id",
                tls_psk_file=temp_name,
            )

            self.assertEqual(
                sender._parse_psk(),
                bytes.fromhex("00112233445566778899AABBCCDDEEFF"),
            )
        finally:
            os.unlink(temp_name)

    def test_parse_psk_invalid_hex(self):
        sender = AsyncSender(
            "server",
            tls_connect="psk",
            tls_psk_identity="id",
            tls_psk="zzzz",
        )

        with self.assertRaises(ValueError):
            sender._parse_psk()
