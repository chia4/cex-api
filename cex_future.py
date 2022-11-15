import requests
from requests_toolbelt.adapters.source import SourceAddressAdapter
import time
import hashlib
import hmac
from urllib.parse import urlencode
import json
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from math import log10
from pprint import pprint


class MexcFuture:
    def __init__(self, ip, key, secret, leverage):
        self.base = "https://contract.mexc.com"
        self.name = "MEXC"
        self.ip = ip
        self.key = key
        self.secret = secret
        self.leverage = leverage
        disable_warnings(InsecureRequestWarning)

    def request(self, method, url, params):
        t = str(int(time.time() * 1000))
        if method == "POST":
            plaintext = self.key + t + json.dumps(params)
        else:
            params_list = []
            for param in params:
                params_list.append(param + "=" + params[param])
            plaintext = self.key + t + "&".join(sorted(params_list))
        signature = hmac.new(self.secret.encode("utf-8"), plaintext.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {
            "ApiKey": self.key,
            "Request-Time": t,
            "Signature": signature,
            "Content-Type": "application/json"
        }
        try:
            session = requests.Session()
            session.mount("https://", SourceAddressAdapter(self.ip))
            if method == "POST":
                request = requests.Request(method, self.base + url, headers, json=params)
            else:
                request = requests.Request(method, self.base + url, headers, params=params)
            prepared = session.prepare_request(request)
            response = session.send(prepared, timeout=5, verify=False).json()
            if response["code"] == 0:
                return True, response
            else:
                return False, response
        except Exception as error:
            return False, error

    def get_position(self, symbol=None):
        while True:
            params = {}
            if symbol:
                params = {"symbol": symbol}
            response = self.request("GET", "/api/v1/private/position/open_positions", params)
            if response[0]:
                if response[1]["data"]:
                    if symbol:
                        long = response[1]["data"][0]["positionType"] == 1
                        return response[1]["data"][0]["holdVol"] if long else -response[1]["data"][0]["holdVol"]
                    else:
                        return True
                else:
                    return 0
            else:
                print(f"mexc get_position: {response[1]}")
            time.sleep(1)

    def change_position_mode(self, position_mode):
        while True:
            params = {"positionMode": position_mode}
            response = self.request("POST", "/api/v1/private/position/change_position_mode", params)
            if response[0]:
                return None
            else:
                print(f"mexc change_position_mode: {response[1]}")
            time.sleep(1)

    def change_leverage(self, symbol):
        params = {
            "leverage": self.leverage,
            "openType": 2,
            "symbol": symbol,
            "positionType": 2
        }
        while True:
            response = self.request("POST", "/api/v1/private/position/change_leverage", params)
            if response[0]:
                return None
            else:
                print(f"mexc change_leverage: {response[1]}")
            time.sleep(1)

    def balance(self):
        while True:
            response = self.request("GET", "/api/v1/private/account/assets", {})
            if response[0]:
                for currency in response[1]["data"]:
                    if currency["currency"] == "USDT":
                        return currency["availableBalance"]
            else:
                print(f"mexc balance: {response[1]}")
            time.sleep(1)

    def order(self, symbol, price, vol, external_order_id, precition):
        params = {
            "symbol": symbol,
            "price": f"{price:.{precition}}",
            "vol": vol if vol > 0 else -vol,
            "leverage": self.leverage,
            "side": 1 if vol > 0 else 3,
            "type": 3,
            "openType": 2,
            "externalOid": external_order_id,
            "positionMode": 2
        }
        t = time.time()
        response = self.request("POST", "/api/v1/private/order/submit", params)
        print(f"mexc order(used {time.time() - t:.3f}s): {response[1]}\n")
        get_order_response = self.get_order(symbol, external_order_id)
        if "data" in get_order_response:
            return get_order_response["data"]["dealVol"]
        else:
            pprint(params)
            return 0

    def get_order(self, symbol, external_order_id):
        while True:
            params = {
                "symbol": symbol,
                "external_oid": external_order_id
            }
            response = self.request("GET", f"/api/v1/private/order/external/{symbol}/{external_order_id}", params)
            if response[0]:
                return response[1]
            else:
                print(f"mexc get_order: {response[1]}")
            time.sleep(1)

    def depth(self, symbol, limit):
        params = {
            "symbol": symbol,
            "limit": str(limit)
        }
        response = self.request("GET", f"/api/v1/contract/depth/{symbol}", params)
        if not response[0]:
            print(f"mexc depth: {response[1]}", end=" " * 20 + "\r")
            return False
        delay = time.time() * 1000 - response[1]["data"]["timestamp"]
        if delay > 120:
            print(f"mexc depth: 获取时间过长，达{delay:.2f}ms", end=" " * 20 + "\r")
            return False
        else:
            return response[1], response[1]["data"]["bids"][0][0], \
                   response[1]["data"]["asks"][0][0], response[1]["data"]["timestamp"] / 1000

    @staticmethod
    def parse_depth(depth, side):
        return depth["data"][side]

    def detail(self, symbol=None):
        params = {}
        if symbol:
            params = {"symbol": symbol}
        response = self.request("GET", "/api/v1/contract/detail", params)
        if response[0]:
            return response[1]
        else:
            print(f"mexc detail: {response[1]}")
            return False

    def contract_multiplie(self, symbol):
        return self.detail(symbol)["data"]["contractSize"]

    def precition(self, symbol):
        return self.detail(symbol)["data"]["priceScale"]


class GateFuture:
    def __init__(self, ip, key, secret, leverage):
        self.base = "https://api.gateio.ws"
        self.name = "GATE"
        self.ip = ip
        self.key = key
        self.secret = secret
        self.leverage = leverage
        # 由于gate默认单向持仓，故不初始化时设置
        disable_warnings(InsecureRequestWarning)

    def request(self, method, url, params, query_post=False):
        payload = "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce" \
                  "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
        query = ""
        if method == "POST" and not query_post:
            payload = hashlib.sha512(json.dumps(params).encode("utf-8")).hexdigest()
        else:
            query = urlencode(params)
        t = str(time.time())
        plaintext = "%s\n%s\n%s\n%s\n%s" % (method, url, query, payload, t)
        signature = hmac.new(self.secret.encode("utf-8"), plaintext.encode("utf-8"), hashlib.sha512).hexdigest()
        headers = {
            "Key": self.key,
            "Timestamp": t,
            "SIGN": signature,
            "Content-Type": "application/json"
        }
        try:
            session = requests.Session()
            session.mount("https://", SourceAddressAdapter(self.ip))
            if method == "POST" and not query_post:
                request = requests.Request(method, self.base + url, headers, json=params)
            else:
                request = requests.Request(method, self.base + url, headers, params=params)
            prepared = session.prepare_request(request)
            response = session.send(prepared, timeout=5, verify=False)
            if response.status_code == 200 or response.status_code == 201:
                return True, response.json()
            else:
                return False, response
        except Exception as error:
            return False, error

    def get_position(self, contract):
        while True:
            response = self.request("GET", f"/api/v4/futures/usdt/positions/{contract}", {})
            if response[0]:
                return response[1]["size"]
            elif response[1].status_code == 400:
                return 0
            else:
                print(f"gate get_position:{contract} {response[1]}")
            time.sleep(1)

    def change_leverage(self, contract):
        params = {
            "leverage": "0",
            "cross_leverage_limit": str(self.leverage)
        }
        while True:
            response = self.request("POST", f"/api/v4/futures/usdt/positions/{contract}/leverage", params, True)
            if response[0]:
                return None
            else:
                print(f"gate change_leverage: {response[1]}")
            time.sleep(1)

    def balance(self):
        while True:
            response = self.request("GET", "/api/v4/futures/usdt/accounts", {})
            if response[0]:
                return float(response[1]["available"])
            else:
                print(f"gate balance: {response[1]}")
            time.sleep(1)

    def order(self, contract, price, size, text, precition):
        params = {
            "contract": contract,
            "size": size,
            "price": f"{price:.{precition}}",
            "tif": "ioc",
            "text": text
        }
        t = time.time()
        response = self.request("POST", "/api/v4/futures/usdt/orders", params)
        print(f"gate order(used {time.time() - t:.3f}s) : {response[1]}\n")
        if response[0]:
            return abs(response[1]["size"] - response[1]["left"])
        else:
            get_order_response = self.get_order(text)
            if get_order_response:
                return abs(get_order_response["size"] - get_order_response["left"])
            else:
                pprint(params)
                return 0

    def get_order(self, text):
        response = self.request("GET", f"/api/v4/futures/usdt/orders/{text}", {})
        while True:
            if response[0]:
                return response[1]
            else:
                if response[1].status_code == 404:
                    return False
                else:
                    print(f"gate get_order: {response[1]}")
            time.sleep(1)

    def depth(self, contract, limit):
        params = {
            "contract": contract,
            "limit": limit
        }
        response = self.request("GET", "/api/v4/futures/usdt/order_book", params)
        if not response[0]:
            print(f"gate depth: {response[1]}", end=" " * 20 + "\r")
            return False
        delay = (time.time() - response[1]["current"]) * 1000
        if delay > 120:
            print(f"gate depth: 获取时间过长，达{delay:.2f}ms", end=" " * 20 + "\r")
            return False
        else:
            return response[1], float(response[1]["bids"][0]["p"]), \
                   float(response[1]["asks"][0]["p"]), response[1]["current"]

    @staticmethod
    def parse_depth(depth, side):
        parsed_depth = []
        for depth_by_line in depth[side]:
            depth_by_line["p"] = float(depth_by_line["p"])
            parsed_depth.append([depth_by_line["p"], depth_by_line["s"]])
        return parsed_depth

    def detail(self, contract=""):
        if contract:
            contract = "/" + contract
        response = self.request("GET", f"/api/v4/futures/usdt/contracts{contract}", {})
        if response[0]:
            return response[1]
        else:
            print(f"gate detail: {response[1]}")
            return False

    def contract_multiplie(self, contract):
        return float(self.detail(contract)["quanto_multiplier"])

    def precition(self, contract):
        return -int(log10(float(self.detail(contract)["order_price_round"])))
