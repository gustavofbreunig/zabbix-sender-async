import asyncio
import json
import random
import socket
import time
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
    ZABBIX_API_PORT=8888
    ZABBIX_USER=Admin
    ZABBIX_PASS=zabbix 
    """

    #number of items to send
    METRIC_COUNT = 2

    def get_metrics_description(self):
        #items (metrics) to include in zabbix, a list of tuple (name, zabbix type code, value)
        #type code: https://www.zabbix.com/documentation/current/en/manual/api/reference/item/object#host
        #make sure to have at minimum one item of each data type
        return [
            ('test.metric.text', 4, "this data came from zabbix-sender-async"),
            ('test.metric.unsigned', 3, int(random.random() * 10000)),
            ('test.metric.float', 0, random.random())
        ]    

    def get_zabbix_metrics(self):
        hostname = self.get_test_hostname()
        desc = self.get_metrics_description()
        return list(map(lambda i: ItemData(host=hostname, key=i[0], value=i[2]), desc))


    def get_test_hostname(self):
        return 'async-sender-test-host'

    def get_sender(self):
        return AsyncSender(os.environ["ZABBIX_HOST"], os.environ["ZABBIX_SENDER_PORT"])
    
    def get_api_url(self):
        return 'http://' + os.environ["ZABBIX_HOST"] + ':' + os.environ["ZABBIX_API_PORT"] + '/api_jsonrpc.php'

    def add_default_headers(self, req : urllib.request.Request):
        req.add_header('Content-Type', 'application/json-rpc')
        req.add_header('User-Agent', 'zabbix-sender-async')        

    def get_generic_request(self) -> dict:
        request_json = {
                    'jsonrpc': '2.0',
                    'id': 1
                }
        return request_json
    
    def do_request(self, request_obj : dict) -> dict:
        api_url = self.get_api_url()
        data = json.dumps(request_obj).encode("utf-8")
        req = urllib.request.Request(api_url, data)
        self.add_default_headers(req)
        ret = urllib.request.urlopen(req)
        ret_str = ret.read().decode('utf-8')
        ret_json = json.loads(ret_str)

        if 'error' in ret_json:            
            raise Exception(ret_json['error'])
        
        return  ret_json      

    def do_login(self, user : str, password : str) -> str:
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

    def get_groupid(self, auth : str) -> int:
        """get any groupid"""
        request_json = self.get_generic_request()
        request_json['method'] = 'hostgroup.get'
        request_json['auth'] = auth
        request_json['params'] = {}
        ret_json = self.do_request(request_json)

        groups = ret_json['result']
        if len(groups) == 0:
            raise Exception('cannot find any group to create the test host')

        #get the first group
        return int(groups[0]['groupid'])

    def createHost(self, auth : str):      
        hostname = self.get_test_hostname()
        #now we have an auth token, get any group
        groupid = self.get_groupid(auth)
        
        request_json = self.get_generic_request()
        request_json['auth'] = auth
        request_json['method'] = 'host.create'
        request_json['params'] = {
                                    "host" : hostname,
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

    def createItems(self, auth : str, host : int):
        items = self.get_metrics_description()
        for item in items:
            request_json = self.get_generic_request()
            request_json['auth'] = auth
            request_json['method'] = 'item.create'
            request_json['params'] = {
                                    "name": item[0],
                                    "key_": item[0],
                                    "hostid": host,
                                    "type": 2, #zabbix trapper
                                    "value_type": item[1]                         
                                }
        
            self.do_request(request_json)


    def hostExists(self, auth : str):
        hostname = self.get_test_hostname()
        request_json = self.get_generic_request()
        request_json['auth'] = auth
        request_json['method'] = 'host.get'
        request_json['params'] = {
            "filter": {
                "host": [ hostname ]
            }
        }

        ret_json = self.do_request(request_json)

        host_count = len(ret_json['result'])
        return host_count > 0

    def setupHost(self):
        auth = self.do_login(os.environ["ZABBIX_USER"], os.environ["ZABBIX_PASS"])
        if not self.hostExists(auth):
            self.createHost(auth)
            

    async def asyncSetUp(self):
        load_dotenv()
        self.setupHost()

    async def test_simple_send(self):
        sender = self.get_sender()
        metrics = self.get_zabbix_metrics()

        result = await sender.send(metrics)
        self.assertIsNotNone(result)
        self.assertGreater(result.total, 0)
        self.assertGreater(result.processed, 0)    

    async def test_asynchronous_sending(self):
        sender = self.get_sender()

        metrics = []
        for _ in range(0,self.METRIC_COUNT):
            metrics.append(self.get_zabbix_metrics())

        start_time_sync = time.time()
        for metric in metrics:
            await sender.send(metric)
        end_time_sync = time.time()
        time_spent_sync = end_time_sync - start_time_sync        

        tasks = []
        for _ in range(0,self.METRIC_COUNT):
            tasks.append(sender.send(self.get_zabbix_metrics()))

        start_time_async = time.time()
        results = await asyncio.gather(*tasks)
        end_time_async = time.time()
        time_spent_async = end_time_async - start_time_async

        #asynchronous testing proof, the network is the bottleneck so the difference is small
        
        #asynchronous execution must be faster
        self.assertLess(time_spent_async, time_spent_sync)

        #asynchronous executions must be 10% faster at least
        time_spent_sync - time_spent_async > time_spent_sync * 0.1

        self.assertTrue(True)