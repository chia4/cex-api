from urllib.parse import urlencode
import time
import hashlib
import hmac
import json
from pprint import pprint
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning


class Mexc:
    def __init__(self, ip, key, secret):
        self.base = "https://www.mexc.com"
        self.name = "MEXC"
        self.ip = ip
        self.key = key
        self.secret = secret
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
            if method == "POST":
                response = self.ip.request(method, self.base + url, json=params, headers=headers)
            else:
                response = self.ip.request(method, self.base + url, params=params, headers=headers)
            response_json = response.json()
            if response_json["code"] == 200:
                return True, response_json
            else:
                return False, response.text
        except Exception as error:
            return False, error

    def buy(self, symbol, price, quantity):
        params = {
            "symbol": symbol,
            "price": "%.10f" % price,
            "quantity": "%.10f" % quantity,
            "trade_type": "BID",
            "order_type": "IMMEDIATE_OR_CANCEL"
        }
        status, response = self.request("POST", "/open/api/v2/order/place", params)
        print("mexc buy :", response)
        return status

    def sell(self, symbol, price, quantity):
        params = {
            "symbol": symbol,
            "price": "%.10f" % price,
            "quantity": "%.10f" % quantity,
            "trade_type": "ASK",
            "order_type": "LIMIT_ORDER"
        }
        status, response = self.request("POST", "/open/api/v2/order/place", params)
        print("mexc sell :", response)
        return status

    def cancel(self, symbol):
        status, response = self.request("DELETE", "/open/api/v2/order/cancel_by_symbol", {"symbol": symbol})
        print("mexc cancel :", response)
        return status

    def tiker(self):
        while True:
            status, response = self.request("GET", "/open/api/v2/market/ticker", {})
            if status:
                price_dict = {}
                for coinTiker in response["data"]:
                    price_dict[coinTiker["symbol"]] = float(coinTiker["last"])
                return price_dict
            else:
                print("mexc tiker :", response)
                time.sleep(1)

    def balance(self, coin, includ_frozen=False):
        while True:
            status, response = self.request("GET", "/open/api/v2/account/info", {})
            if status:
                if response["data"]:
                    if coin in response["data"]:
                        if includ_frozen:
                            available = float(response["data"][coin]["available"])
                            return available + float(response["data"][coin]["frozen"])
                        else:
                            return float(response["data"][coin]["available"])
                    else:
                        return 0
            print("mexc balance :", response)
            time.sleep(1)

    # amount函数统计过去一小时某交易对在买/卖方向上成交金额(以USDT记且不统计还没有结束的订单)
    def amount(self, symbol, side):
        if side == "buy":
            trade_type = "BID"
        else:
            trade_type = "ASK"
        while True:
            sign = True
            usdt = 0
            for states in ["FILLED", "PARTIALLY_CANCELED"]:
                params = {
                    "symbol": symbol,
                    "start_time": str(int(time.time() - 36000)),
                    "trade_type": trade_type,
                    "states": states
                }
                status, response = self.request("GET", "/open/api/v2/order/list", params)
                if not status:
                    print("mexc amount :", response)
                    sign = False
                    break
                for order in response["data"]:
                    usdt += float(order["deal_amount"])
            if not sign:
                time.sleep(1)
                continue
            return usdt

    def price(self, symbol):
        return self.tiker().get(symbol)


class Gate:
    def __init__(self, ip, key, secret):
        self.base = "https://api.gateio.ws"
        self.name = "GATE"
        self.ip = ip
        self.key = key
        self.secret = secret
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
            if method == "POST" and not query_post:
                response = self.ip.request(method, self.base + url, json=params, headers=headers)
            else:
                response = self.ip.request(method, self.base + url, params=params, headers=headers)
            if response.status_code == 200 or response.status_code == 201:
                return True, response.json()
            else:
                return False, response.text
        except Exception as error:
            return False, error

    def buy(self, symbol, price, amount):
        params = {
            "currency_pair": symbol,
            "side": "buy",
            "amount": "%.10f" % amount,
            "price": "%.10f" % price,
            "time_in_force": "ioc"
        }
        status, response = self.request("POST", "/api/v4/spot/orders", params)
        print("gate buy :")
        pprint(response, sort_dicts=False)
        return status

    def sell(self, symbol, price, amount):
        params = {
            "currency_pair": symbol,
            "side": "sell",
            "amount": "%.10f" % amount,
            "price": "%.10f" % price
        }
        status, response = self.request("POST", "/api/v4/spot/orders", params)
        print("gate sell :")
        pprint(response, sort_dicts=False)
        return status

    def cancel(self, symbol):
        status, response = self.request("DELETE", "/api/v4/spot/orders", {"currency_pair": symbol})
        print("gate cancel :")
        pprint(response, sort_dicts=False)
        return status

    def tiker(self):
        while True:
            status, response = self.request("GET", "/api/v4/spot/tickers", {})
            if status:
                price_dict = {}
                for coinTiker in response:
                    price_dict[coinTiker["currency_pair"]] = float(coinTiker["last"])
                return price_dict
            else:
                print("gate tiker :", response)
            time.sleep(1)

    def balance(self, coin, include_locked=False):
        while True:
            status, response = self.request("GET", "/api/v4/spot/accounts", {})
            if status:
                for account in response:
                    if account["currency"] == coin:
                        if include_locked:
                            return float(account["available"]) + float(account["locked"])
                        else:
                            return float(account["available"])
                return 0
            else:
                print("gate balance :", response)
            time.sleep(1)

    # amount函数统计过去一小时某交易对在买/卖方向上成交金额(以USDT记且不统计还没有结束的订单)
    def amount(self, symbol, side):
        while True:
            usdt = 0
            params = {
                "currency_pair": symbol,
                "status": "finished",
                "from": str(int(time.time() - 36000)),
                "side": side
            }
            status, response = self.request("GET", "/api/v4/spot/orders", params)
            if not status:
                print("gate amount :", response)
                time.sleep(1)
                continue
            for order in response:
                usdt += float(order["filled_total"])
            return usdt

    def price(self, symbol):
        return self.tiker().get(symbol)
