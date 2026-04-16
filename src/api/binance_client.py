import time
import hmac
import hashlib
import requests
import json

class BinanceClient:
    def __init__(self, api_key, api_secret, base_url="https://fapi.binance.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": api_key
        })
        self.last_request_time = 0
        self.rate_limit = 1  # 限制1秒内最多1个请求
        self.connect_timeout = 5
        self.read_timeout = 20
        self.max_retries = 2
        self.retry_backoff = 0.8
        self._lot_size_cache = {}  # 缓存各交易对的 LOT_SIZE
        self._hedge_mode = None  # 缓存持仓模式：True=双向, False=单向

    def _wait_for_rate_limit(self):
        """等待速率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    def _sign_request(self, params):
        """签名请求"""
        timestamp = int(time.time() * 1000)
        params["timestamp"] = timestamp
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method, endpoint, params=None, signed=False):
        """统一请求入口：限速 + 超时 + 简单重试"""
        self._wait_for_rate_limit()
        request_params = params.copy() if isinstance(params, dict) else {}
        if signed:
            request_params = self._sign_request(request_params)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=self.base_url + endpoint,
                    params=request_params,
                    timeout=(self.connect_timeout, self.read_timeout),
                )
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2 ** attempt))
                    continue
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2 ** attempt))
                    continue
                raise Exception(f"Binance 请求失败: {e}") from e
        raise Exception(f"Binance 请求失败: {last_error}")
    
    def get_position_mode(self):
        """获取持仓模式：True=双向持仓, False=单向持仓"""
        if self._hedge_mode is not None:
            return self._hedge_mode
        endpoint = "/fapi/v1/positionSide/dual"
        response = self._request("GET", endpoint, params={}, signed=True)
        data = response.json()
        self._hedge_mode = data.get("dualSidePosition", False)
        return self._hedge_mode
    
    def change_position_mode(self, dual_side):
        """切换持仓模式：dual_side=True 双向, False 单向"""
        endpoint = "/fapi/v1/positionSide/dual"
        params = {"dualSidePosition": str(dual_side).lower()}
        response = self._request("POST", endpoint, params=params, signed=True)
        data = response.json()
        if data.get("code") == 0 or response.ok:
            self._hedge_mode = dual_side
            return True
        return False

    def get_exchange_info(self):
        """获取交易所信息（含 LOT_SIZE）"""
        endpoint = "/fapi/v1/exchangeInfo"
        response = self._request("GET", endpoint)
        response.raise_for_status()
        return response.json()

    def get_symbol_lot_size(self, symbol):
        """获取交易对的 minQty 和 stepSize，用于正确格式化订单数量"""
        if symbol in self._lot_size_cache:
            return self._lot_size_cache[symbol]
        try:
            info = self.get_exchange_info()
            for s in info.get("symbols", []):
                if s["symbol"] == symbol:
                    for f in s.get("filters", []):
                        if f.get("filterType") == "LOT_SIZE":
                            result = {
                                "minQty": float(f["minQty"]),
                                "stepSize": float(f["stepSize"]),
                            }
                            self._lot_size_cache[symbol] = result
                            return result
        except Exception as e:
            print(f"获取 {symbol} LOT_SIZE 失败: {e}")
        # 默认精度：BTC 3位，ETH 2位，其他 2位
        defaults = {"BTCUSDT": 0.001, "ETHUSDT": 0.01}
        step = defaults.get(symbol, 0.01)
        result = {"minQty": step, "stepSize": step}
        self._lot_size_cache[symbol] = result
        return result

    def get_klines(self, symbol, interval, limit=100):
        """获取K线数据"""
        endpoint = "/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = self._request("GET", endpoint, params=params)
        return response.json()
    
    def get_ticker(self, symbol):
        """获取行情数据"""
        endpoint = "/fapi/v1/ticker/24hr"
        params = {
            "symbol": symbol
        }
        response = self._request("GET", endpoint, params=params)
        try:
            data = response.json()
            # 确保返回的是字典类型
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and len(data) > 0:
                # 如果返回的是列表且非空，返回第一个元素
                return data[0]
            else:
                # 如果返回的不是预期格式，返回空字典
                print(f"警告: get_ticker 返回非预期格式: {type(data)}")
                return {}
        except Exception as e:
            print(f"解析get_ticker响应失败: {e}")
            return {}
    
    def get_funding_rate(self, symbol):
        """获取资金费率（返回最新一条，API 按时间升序返回）"""
        endpoint = "/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": 10}
        response = self._request("GET", endpoint, params=params)
        try:
            data = response.json()
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and len(data) > 0:
                return data[-1]  # 最新一条
            else:
                return {}
        except Exception as e:
            print(f"解析get_funding_rate响应失败: {e}")
            return {}
    
    def get_account(self):
        """获取账户信息"""
        endpoint = "/fapi/v2/account"
        response = self._request("GET", endpoint, params={}, signed=True)
        return response.json()
    
    def get_position_risk(self):
        """获取持仓信息"""
        endpoint = "/fapi/v2/positionRisk"
        response = self._request("GET", endpoint, params={}, signed=True)
        try:
            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "code" in data and data.get("code") != 0:
                    print(f"get_position_risk API 错误: {data.get('msg', data)}")
                    return []
                if "positions" in data:
                    return data.get("positions", [])
            return []
        except Exception as e:
            print(f"解析get_position_risk响应失败: {e}")
            return []
    
    def set_leverage(self, symbol, leverage):
        """设置杠杆"""
        endpoint = "/fapi/v1/leverage"
        params = {
            "symbol": symbol,
            "leverage": leverage
        }
        response = self._request("POST", endpoint, params=params, signed=True)
        return response.json()
    
    def create_order(self, symbol, side, type_, quantity, price=None, stop_price=None, position_side=None):
        """创建订单。position_side: 双向持仓时必填 LONG/SHORT，单向时用 BOTH 或不传。
        STOP_MARKET/TAKE_PROFIT_MARKET 只需 stopPrice，触发后以市价成交，更可靠。"""
        endpoint = "/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": side,
            "type": type_,
            "quantity": quantity
        }
        if self.get_position_mode():
            if not position_side:
                raise Exception("双向持仓模式下必须指定 positionSide (LONG/SHORT)")
            params["positionSide"] = position_side
        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        if type_ in ["LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"]:
            params["timeInForce"] = "GTC"
        if type_ in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
            pass  # 无需 price、timeInForce
        response = self._request("POST", endpoint, params=params, signed=True)
        data = response.json()
        if not response.ok:
            raise Exception(f"Binance API 错误: {data.get('msg', response.text)} (code: {data.get('code', '')})")
        if "code" in data and data["code"] != 0:
            raise Exception(f"Binance API 错误: {data.get('msg', '')} (code: {data.get('code', '')})")
        return data
    
    def cancel_order(self, symbol, order_id=None, orig_client_order_id=None):
        """取消订单"""
        endpoint = "/fapi/v1/order"
        params = {
            "symbol": symbol
        }
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        response = self._request("DELETE", endpoint, params=params, signed=True)
        return response.json()
    
    def get_open_orders(self, symbol=None):
        """获取未成交订单"""
        endpoint = "/fapi/v1/openOrders"
        params = {}
        if symbol:
            params["symbol"] = symbol
        response = self._request("GET", endpoint, params=params, signed=True)
        return response.json()

    def cancel_all_open_orders(self, symbol):
        """取消该交易对下所有未成交订单（含止盈止损）"""
        endpoint = "/fapi/v1/allOpenOrders"
        params = {"symbol": symbol}
        response = self._request("DELETE", endpoint, params=params, signed=True)
        return response.json()