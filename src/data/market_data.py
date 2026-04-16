import pandas as pd
from api.binance_client import BinanceClient
from utils.indicators import Indicators

class MarketDataManager:
    def __init__(self, binance_client):
        self.binance_client = binance_client
        self.indicators = Indicators()
    
    def get_klines_data(self, symbol, interval, limit=100):
        """获取K线数据并转换为DataFrame"""
        klines = self.binance_client.get_klines(symbol, interval, limit)
        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.astype({
            "open": float, "high": float, "low": float, "close": float, "volume": float
        })
        df.set_index("timestamp", inplace=True)
        return df
    
    def get_market_data(self, symbol, intervals=["5m", "15m", "1h", "4h", "1d"]):
        """获取多周期市场数据"""
        market_data = {}
        for interval in intervals:
            df = self.get_klines_data(symbol, interval)
            market_data[interval] = {
                "df": df,
                "indicators": self.calculate_indicators(df)
            }
        return market_data
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        close_prices = df["close"]
        high_prices = df["high"]
        low_prices = df["low"]
        
        indicators = {
            "rsi": self.indicators.calculate_rsi(close_prices),
            "macd": self.indicators.calculate_macd(close_prices),
            "ema20": self.indicators.calculate_ema(close_prices, 20),
            "ema50": self.indicators.calculate_ema(close_prices, 50),
            "sma20": self.indicators.calculate_sma(close_prices, 20),
            "sma50": self.indicators.calculate_sma(close_prices, 50),
            "atr": self.indicators.calculate_atr(high_prices, low_prices, close_prices),
            "bollinger_bands": self.indicators.calculate_bollinger_bands(close_prices),
            "kdj": self.indicators.calculate_kdj(high_prices, low_prices, close_prices),
            "mfi": self.indicators.calculate_mfi(high_prices, low_prices, close_prices, df["volume"])
        }
        return indicators
    
    def get_ticker_data(self, symbol):
        """获取行情数据"""
        return self.binance_client.get_ticker(symbol)
    
    def get_funding_rate(self, symbol):
        """获取资金费率"""
        return self.binance_client.get_funding_rate(symbol)
    
    def get_recent_klines(self, symbol, interval, limit=18):
        """获取最近的K线数据"""
        df = self.get_klines_data(symbol, interval, limit)
        return df.tail(limit)
    
    def analyze_market(self, symbol):
        """综合分析市场"""
        try:
            market_data = self.get_market_data(symbol)
            ticker_data = self.get_ticker_data(symbol)
            funding_rate = self.get_funding_rate(symbol)
            price = float(ticker_data.get("lastPrice", 0) or 0)
            if price <= 0:
                print(f"警告: {symbol} 价格无效，跳过")
                return None
            analysis = {
                "symbol": symbol,
                "price": price,
                "24h_change": float(ticker_data.get("priceChangePercent", 0) or 0),
                "volume": float(ticker_data.get("volume", 0) or 0),
                "funding_rate": float(funding_rate.get("fundingRate", 0) or 0),
                "market_data": market_data
            }
            return analysis
        except Exception as e:
            print(f"市场分析失败 {symbol}: {e}")
            return None