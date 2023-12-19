from unittest import TestCase

from zabbixasync.sender import AsyncSender


class TestResponsePayload(TestCase):
    def setUp(self):
        self.sender = AsyncSender('server')

    def test_response_parse(self):
        payload_received = b'{"response":"success","info":"processed: 1; \
failed: 2; total: 3; seconds spent: 0.123456"}'
        response_sucess_expected = 'success'
        response_processed_expected = 1
        response_failed_expected = 2
        response_total_expected = 3
        response_seconds_spent_expected = 0.123456

        resp = self.sender._parse_response(payload_received)
        self.assertEqual(resp.response, response_sucess_expected)
        self.assertEqual(resp.processed, response_processed_expected)
        self.assertEqual(resp.failed, response_failed_expected)
        self.assertEqual(resp.total, response_total_expected)
        self.assertEqual(resp.seconds_spent, response_seconds_spent_expected)
