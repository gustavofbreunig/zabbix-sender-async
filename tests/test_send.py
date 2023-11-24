import asyncio
import json
import socket
from dotenv import load_dotenv
from unittest import IsolatedAsyncioTestCase
import os
import urllib.request

from zabbixasync.sender import AsyncSender, ItemData

class TestSend(IsolatedAsyncioTestCase):
    """
    Test async operations. 
    Configure all variables according to your enrivonment in a .env file:
    ZABBIX_HOST=localhost
    ZABBIX_PORT=10051
    ZABBIX_USER=Admin
    ZABBIX_PASS=zabbix
    """

    def add_default_headers(self, req : urllib.request.Request):
        req.add_header('Content-Type', 'application/json-rpc')
        req.add_header('User-Agent', 'zabbix-sender-async')        

    def do_login(self, url : str, user : str, password : str) -> str:
        request_json = {
                    'jsonrpc': '2.0',
                    'method': 'user.login',
                    'params': {
                                "username": user,
                                "password": password
                            },
                    'id': 1
                }

        data = json.dumps(request_json).encode("utf-8")
        req = urllib.request.Request(url, data)
        self.add_default_headers(req)
        ret = urllib.request.urlopen(req)
        ret_str = ret.read().decode('utf-8')
        ret_json = json.loads(ret_str)

        if 'error' in ret_json:
            raise Exception(ret_json['error'])
        
        return ret_json['result']
        

    def createHost(self):
        auth = self.do_login(self.api_url, os.environ["ZABBIX_USER"], os.environ["ZABBIX_PASS"])    
        
        #now we have an auth token
        request_json['auth'] = ret_json['result']

        request_json['method'] = 'host.create'

        request_json['params'] = {  "host" : self.hostname,
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
                                                "groupid": "1"
                                            }
                                        ]
                                }

        data = json.dumps(request_json).encode("utf-8")
        req = urllib.request.Request(url, data)
        req.add_header('Content-Type', 'application/json-rpc')
        req.add_header('User-Agent', 'zabbix-sender-async')
        ret = urllib.request.urlopen(req)
        ret_str = ret.read().decode('utf-8')
        ret_json = json.loads(ret_str)        

    async def asyncSetUp(self):
        load_dotenv()
        self.sender = AsyncSender(os.environ["ZABBIX_HOST"], os.environ["ZABBIX_SENDER_PORT"])
        self.api_url = 'http://' + os.environ["ZABBIX_HOST"] + ':' + os.environ["ZABBIX_API_PORT"] + '/api_jsonrpc.php'
        self.hostname = socket.gethostname()
        self.createHost()

    async def test_unique_simple_send(self):
        result = await self.sender.send(ItemData(self.hostname, 'metric.example', "test"))
        self.assertIsNotNone(result)
        self.assertGreater(result.total, 0)
        self.assertGreater(result.processed, 0)
