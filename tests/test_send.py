import asyncio
import json
import os
import random
import string
import time
import urllib.request

from dotenv import load_dotenv
import pytest

from zabbixasync.sender import AsyncSender, ItemData


class TestSend:
    """
    Integration tests for Zabbix sender against a running Zabbix 7 instance.
    First, it creates a host using the Zabbix API, then send various metrics.

    Required environment variables:
    - ZABBIX_HOST
    - ZABBIX_API_PORT
    - ZABBIX_SENDER_PORT
    - ZABBIX_USER
    - ZABBIX_PASS

    Optional TLS-PSK variables:
    - ZABBIX_TLS_CONNECT=psk
    - ZABBIX_TLS_PSK_IDENTITY
    - ZABBIX_TLS_PSK or ZABBIX_TLS_PSK_FILE
    """

    REQUIRED_ENV_VARS = [
        "ZABBIX_HOST",
        "ZABBIX_API_PORT",
        "ZABBIX_SENDER_PORT",
        "ZABBIX_USER",
        "ZABBIX_PASS",
    ]
    ZBX_UNABLE_CONFIG = "Unable to select configuration."

    def get_metrics_description(self):
        # type codes:
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/item/object
        return [
            ("test.metric.text", 4, self.generate_random_string(255)),
            ("test.metric.unsigned", 3, int(random.random() * 10000)),
            ("test.metric.float", 0, random.random()),
        ]

    def generate_random_string(self, size: int) -> str:
        return "".join(random.choices(string.ascii_lowercase, k=size))

    def get_zabbix_metrics(self, number_of_metrics=1):
        metrics = []
        for i in range(number_of_metrics):
            hostname = self.get_test_hostname()
            desc = self.get_metrics_description()[i % 3]
            metrics.append(ItemData(host=hostname, key=desc[0], value=desc[2]))
        return metrics

    def get_test_hostname(self):
        return "async-sender-test-host"

    def get_sender(self):
        kwargs = {}
        tls_connect = os.getenv("ZABBIX_TLS_CONNECT")
        if tls_connect:
            kwargs["tls_connect"] = tls_connect
            kwargs["tls_psk_identity"] = os.getenv("ZABBIX_TLS_PSK_IDENTITY")
            tls_psk = os.getenv("ZABBIX_TLS_PSK")
            tls_psk_file = os.getenv("ZABBIX_TLS_PSK_FILE")
            if tls_psk:
                kwargs["tls_psk"] = tls_psk
            if tls_psk_file:
                kwargs["tls_psk_file"] = tls_psk_file

        return AsyncSender(
            os.environ["ZABBIX_HOST"],
            int(os.environ["ZABBIX_SENDER_PORT"]),
            **kwargs,
        )

    def get_api_url(self):
        return "".join(
            [
                "http://",
                os.environ["ZABBIX_HOST"],
                ":",
                os.environ["ZABBIX_API_PORT"],
                "/api_jsonrpc.php",
            ]
        )

    def add_default_headers(self, req: urllib.request.Request):
        req.add_header("Content-Type", "application/json-rpc")
        req.add_header("User-Agent", "zabbix-sender-async")

    def get_generic_request(self) -> dict:
        return {"jsonrpc": "2.0", "id": 1}

    def do_request(self, request_obj: dict) -> dict:
        api_url = self.get_api_url()
        data = json.dumps(request_obj).encode("utf-8")
        req = urllib.request.Request(api_url, data)
        self.add_default_headers(req)
        ret = urllib.request.urlopen(req, timeout=20)
        ret_str = ret.read().decode("utf-8")
        ret_json = json.loads(ret_str)

        if (
            "error" in ret_json
            and ret_json["error"]["code"] == 1
            and ret_json["error"]["message"] == self.ZBX_UNABLE_CONFIG
        ):
            # server may still be warming up
            time.sleep(10)
            return self.do_request(request_obj)
        if "error" in ret_json:
            raise Exception(ret_json["error"]["message"])

        return ret_json

    def do_login(self, user: str, password: str) -> str:
        request_json = self.get_generic_request()
        request_json["method"] = "user.login"
        request_json["params"] = {
            "username": user,
            "password": password,
        }

        ret_json = self.do_request(request_json)
        if "error" in ret_json:
            raise Exception(ret_json["error"])
        return ret_json["result"]

    def wait_api_ready(self) -> None:
        # Zabbix API version call does not require auth.
        request_json = self.get_generic_request()
        request_json["method"] = "apiinfo.version"
        request_json["params"] = {}
        last_error = None
        for _ in range(24):
            try:
                self.do_request(request_json)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(5)
        raise RuntimeError(f"Zabbix API did not become ready: {last_error}")

    def get_groupid(self, auth: str) -> int:
        request_json = self.get_generic_request()
        request_json["method"] = "hostgroup.get"
        request_json["auth"] = auth
        request_json["params"] = {"output": ["groupid"], "limit": 1}
        ret_json = self.do_request(request_json)

        groups = ret_json["result"]
        if len(groups) == 0:
            raise Exception("cannot find any group to create the test host")
        return int(groups[0]["groupid"])

    def create_host(self, auth: str):
        hostname = self.get_test_hostname()
        groupid = self.get_groupid(auth)

        request_json = self.get_generic_request()
        request_json["auth"] = auth
        request_json["method"] = "host.create"
        request_json["params"] = {
            "host": hostname,
            "interfaces": [
                {
                    "type": 1,
                    "main": 1,
                    "useip": 1,
                    "ip": "127.0.0.1",
                    "dns": "",
                    "port": "10050",
                }
            ],
            "groups": [{"groupid": groupid}],
        }

        ret_json = self.do_request(request_json)
        hostid = int(ret_json["result"]["hostids"][0])
        self.create_items(auth, hostid)

    def create_items(self, auth: str, host: int):
        for item in self.get_metrics_description():
            request_json = self.get_generic_request()
            request_json["auth"] = auth
            request_json["method"] = "item.create"
            request_json["params"] = {
                "name": item[0],
                "key_": item[0],
                "hostid": host,
                "type": 2,  # zabbix trapper
                "value_type": item[1],
            }
            self.do_request(request_json)

    def host_exists(self, auth: str):
        hostname = self.get_test_hostname()
        request_json = self.get_generic_request()
        request_json["auth"] = auth
        request_json["method"] = "host.get"
        request_json["params"] = {
            "filter": {"host": [hostname]},
            "output": ["hostid"],
            "limit": 1,
        }

        ret_json = self.do_request(request_json)
        return len(ret_json["result"]) > 0

    def validate_environment_variables(self):
        missing = [e for e in self.REQUIRED_ENV_VARS if e not in os.environ]
        if missing:
            pytest.skip(
                f"missing integration env vars: {missing}. "
                "Set them to run Zabbix integration tests."
            )

    def setup_host(self):
        self.wait_api_ready()
        auth = self.do_login(os.environ["ZABBIX_USER"], os.environ["ZABBIX_PASS"])
        if not self.host_exists(auth):
            self.create_host(auth)
            # wait for zabbix to persist host and items
            time.sleep(10)

    @pytest.fixture(autouse=True)
    def setup(self):
        load_dotenv()
        self.validate_environment_variables()
        self.setup_host()

    async def test_simple_send(self):
        sender = self.get_sender()
        metrics = self.get_zabbix_metrics()

        result = await sender.send(metrics)
        assert result is not None
        assert result.response == "success"
        assert result.total == 1
        assert result.processed == 1

    async def test_fail_send(self):
        sender = self.get_sender()
        invalid_data = ItemData("invalid_host", "invalid.metric", 0)
        result = await sender.send(invalid_data)

        assert result is not None
        assert result.response == "success"
        assert result.failed == 1

    async def test_big_chunk(self):
        metrics_count = 1000
        sender = self.get_sender()
        metrics = []

        dummy_metrics = self.get_zabbix_metrics(metrics_count)
        [metrics.append(dummy_metric) for dummy_metric in dummy_metrics]

        assert len(metrics) == metrics_count

        start = time.time()
        response = await asyncio.gather(sender.send(metrics))
        end = time.time()
        duration_first_send = end - start

        assert response[0] is not None
        assert response[0].response == "success"
        assert response[0].processed == metrics_count
        assert duration_first_send > 0

        tasks = [sender.send(metrics), sender.send(metrics), sender.send(metrics)]

        start = time.time()
        response = await asyncio.gather(*tasks)
        end = time.time()
        duration_second_send = end - start

        assert duration_second_send < (duration_first_send * 3)

    async def test_long_running_task(self):
        sleep_time = 3
        sender = self.get_sender()

        tasks = []
        tasks.append(asyncio.sleep(sleep_time))
        tasks.append(asyncio.sleep(sleep_time / 2))
        tasks.append(asyncio.sleep(sleep_time / 3))
        tasks.append(asyncio.sleep(sleep_time / 4))
        tasks.append(asyncio.sleep(sleep_time / 5))
        tasks.append(sender.send(self.get_zabbix_metrics()))

        start = time.time()
        await asyncio.gather(*tasks)
        end = time.time()

        execution_time = end - start
        assert execution_time <= sleep_time + 0.05

    async def test_big_metric(self):
        sender = self.get_sender()
        items = []

        for _ in range(5000):
            for metric in self.get_zabbix_metrics():
                items.append(metric)

        response = await sender.send(items)
        assert response is not None
        assert response.processed == 5000
        assert response.response == "success"

    async def test_psk_host(self):
        os.environ['ZABBIX_TLS_CONNECT'] = 'psk'
        os.environ['ZABBIX_TLS_PSK_IDENTITY'] = 'psk001'
        os.environ['ZABBIX_TLS_PSK'] = '578ad7af47cdfc9f73b41e6ee4d68587b351506b70613b0c21758178bef20587'

        sender = self.get_sender()
        metrics = self.get_zabbix_metrics()

        result = await sender.send(metrics)
        assert result is not None
        assert result.response == "success"
        assert result.total == 1
        assert result.processed == 1
