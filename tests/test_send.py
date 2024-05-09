import asyncio
import json
import logging
import random
import string
import time
from dotenv import load_dotenv
import os
import urllib.request

import pytest

from zabbixasync.sender import AsyncSender, ItemData


class TestSend():
    """
    Test async operations.
    Configure all variables according to your enrivonment in a .env file:
    ZABBIX_HOST=localhost
    ZABBIX_PORT=10051
    ZABBIX_API_PORT=8888
    ZABBIX_USER=Admin
    ZABBIX_PASS=zabbix
    """

    ZBX_UNABLE_CONFIG = 'Unable to select configuration.'

    def get_metrics_description(self):
        # items (metrics) to include in zabbix, a list of tuple:
        # (name, zabbix type code, value)
        # type code:
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/item/object#host
        # make sure to have at minimum one item of each data type
        return [
            ('test.metric.text', 4, self.generate_random_string(255)),
            ('test.metric.unsigned', 3, int(random.random() * 10000)),
            ('test.metric.float', 0, random.random())
        ]

    def generate_random_string(self, size: int) -> str:
        return ''.join(random.choices(string.ascii_lowercase, k=size))

    def get_zabbix_metrics(self, number_of_metrics = 1):
        # generate random metrics
        metrics = []
        for i in range(number_of_metrics):
            hostname = self.get_test_hostname()
            desc = self.get_metrics_description()[i % 3]
            metrics.append(ItemData(host=hostname, key=desc[0], value=desc[2])) 
        return metrics

    def get_test_hostname(self):
        return 'async-sender-test-host'

    def get_sender(self):
        return AsyncSender(
            os.environ["ZABBIX_HOST"],
            os.environ["ZABBIX_SENDER_PORT"])

    def get_api_url(self):
        return ''.join(['http://',
                        os.environ["ZABBIX_HOST"],
                        ':',
                        os.environ["ZABBIX_API_PORT"],
                        '/api_jsonrpc.php'])

    def add_default_headers(self, req: urllib.request.Request):
        req.add_header('Content-Type', 'application/json-rpc')
        req.add_header('User-Agent', 'zabbix-sender-async')

    def get_generic_request(self) -> dict:
        request_json = {
                    'jsonrpc': '2.0',
                    'id': 1
                }
        return request_json

    def do_request(self, request_obj: dict) -> dict:
        api_url = self.get_api_url()
        data = json.dumps(request_obj).encode("utf-8")
        req = urllib.request.Request(api_url, data)
        self.add_default_headers(req)
        ret = urllib.request.urlopen(req)
        ret_str = ret.read().decode('utf-8')
        ret_json = json.loads(ret_str)

        if 'error' in ret_json and \
                ret_json['error']['code'] == 1 and \
                ret_json['error']['message'] == self.ZBX_UNABLE_CONFIG:
            # server not ready yet, try again after 10 seconds using recursion
            time.sleep(10)
            return self.do_request(request_obj)
        elif 'error' in ret_json:
            raise Exception(ret_json['error']['message'])

        return ret_json

    def do_login(self, user: str, password: str) -> str:
        """
        Do a login and return the auth token
        """
        request_json = self.get_generic_request()
        request_json['method'] = 'user.login'
        request_json['params'] = {
                                    "username": user,
                                    "password": password
                                }

        ret_json = self.do_request(request_json)

        if 'error' in ret_json:
            raise Exception(ret_json['error'])

        return ret_json['result']

    def get_groupid(self, auth: str) -> int:
        """get any groupid"""
        request_json = self.get_generic_request()
        request_json['method'] = 'hostgroup.get'
        request_json['auth'] = auth
        request_json['params'] = {}
        ret_json = self.do_request(request_json)

        groups = ret_json['result']
        if len(groups) == 0:
            raise Exception('cannot find any group to create the test host')

        # get the first group
        return int(groups[0]['groupid'])

    def createHost(self, auth: str):
        hostname = self.get_test_hostname()
        # now we have an auth token, get any group
        groupid = self.get_groupid(auth)

        request_json = self.get_generic_request()
        request_json['auth'] = auth
        request_json['method'] = 'host.create'
        request_json['params'] = {
                                    "host": hostname,
                                    "interfaces": [
                                        {
                                            "type": 1,
                                            "main": 1,
                                            "useip": 1,
                                            "ip": "127.0.0.1",
                                            "dns": "",
                                            "port": "10050"
                                        }],
                                    "groups": [
                                                {
                                                    "groupid": groupid
                                                }
                                            ]
                                }

        ret_json = self.do_request(request_json)

        hostid = int(ret_json['result']['hostids'][0])

        self.createItems(auth, hostid)

    def createItems(self, auth: str, host: int):
        items = self.get_metrics_description()
        for item in items:
            request_json = self.get_generic_request()
            request_json['auth'] = auth
            request_json['method'] = 'item.create'
            request_json['params'] = {
                                    "name": item[0],
                                    "key_": item[0],
                                    "hostid": host,
                                    "type": 2,  # zabbix trapper
                                    "value_type": item[1]
                                }

            self.do_request(request_json)

    def hostExists(self, auth: str):
        hostname = self.get_test_hostname()
        request_json = self.get_generic_request()
        request_json['auth'] = auth
        request_json['method'] = 'host.get'
        request_json['params'] = {
            "filter": {
                "host": [hostname]
            }
        }

        ret_json = self.do_request(request_json)

        host_count = len(ret_json['result'])
        return host_count > 0

    def validateEnvironmentVariables(self):
        vars = ['ZABBIX_HOST', 'ZABBIX_API_PORT',
                'ZABBIX_SENDER_PORT', 'ZABBIX_USER',
                'ZABBIX_PASS']

        env = list(os.environ)

        match = [e for e in vars if e not in env]

        if len(match) > 0:
            raise Exception(f'Environment variables not found: {match}')

    def setupHost(self):
        auth = self.do_login(
            os.environ["ZABBIX_USER"], os.environ["ZABBIX_PASS"])
        if not self.hostExists(auth):
            self.createHost(auth)

    @pytest.fixture
    def setup(self):
        load_dotenv()
        self.validateEnvironmentVariables()
        self.setupHost()

    async def test_simple_send(self, setup):
        sender = self.get_sender()
        metrics = self.get_zabbix_metrics()

        result = await sender.send(metrics)
        assert result is not None
        assert result.response == 'success'
        assert result.total == 1
        assert result.processed == 1

    async def test_fail_send(self, setup):
        sender = self.get_sender()
        invalid_data = ItemData('invalid_host', 'invalid.metric', 0)
        result = await sender.send(invalid_data)

        assert result is not None
        assert result.response == 'success'
        assert result.failed == 1

    async def test_big_chunk(self, setup):
        # send 1 big packet with 1000 metrics and calculate processing time
        # then create a 3 big packets with 1000 metrics each
        # and send asynchronously
        # the total processed time must be almost the same 
        METRICS = 1000
        sender = self.get_sender()
        metrics = []

        dummy_metrics = self.get_zabbix_metrics(METRICS)
        [metrics.append(dummy_metric) for dummy_metric in dummy_metrics] 

        assert len(metrics) == METRICS

        start = time.time()
        response = await asyncio.gather(sender.send(metrics))
        end = time.time()
        duration_first_send = end - start

        assert response[0] is not None
        assert response[0].response == 'success'
        assert response[0].processed == METRICS
        assert duration_first_send  > 0

        tasks = [sender.send(metrics), sender.send(metrics), sender.send(metrics)]

        start = time.time()
        response = await asyncio.gather(*tasks)
        end = time.time()
        duration_second_send = end - start

        assert duration_second_send  < (duration_first_send * 3)


# send metrics along some long running task, the final time
# must be the longest
    async def test_long_running_task(self, setup):
        SLEEP_TIME = 3
        sender = self.get_sender()

        tasks = []
        tasks.append(asyncio.sleep(SLEEP_TIME))
        tasks.append(asyncio.sleep(SLEEP_TIME / 2))
        tasks.append(asyncio.sleep(SLEEP_TIME / 3))
        tasks.append(asyncio.sleep(SLEEP_TIME / 4))
        tasks.append(asyncio.sleep(SLEEP_TIME / 5))
        tasks.append(sender.send(self.get_zabbix_metrics()))

        start = time.time()
        await asyncio.gather(*tasks)
        end = time.time()

        execution_time = end - start
        assert execution_time <= SLEEP_TIME + 0.01


    async def test_big_metric(self, setup):
        sender = self.get_sender()
        items = []

        for _ in range(5000):
            for metric in self.get_zabbix_metrics():
                items.append(metric)

        response = await sender.send(items)
        assert response is not None
        assert response.processed == 5000
        assert response.response == 'success'

        