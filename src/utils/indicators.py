import numpy as np
import pandas as pd

class Indicators:
    @staticmethod
    def calculate_rsi(prices, period=14):
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else None
    
    @staticmethod
    def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
        """计算MACD指标"""
        ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=slow_period, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        return {
            "macd": macd.iloc[-1] if not macd.empty else None,
            "signal": signal.iloc[-1] if not signal.empty else None,
            "histogram": histogram.iloc[-1] if not histogram.empty else None
        }
    
    @staticmethod
    def calculate_ema(prices, period=20):
        """计算EMA指标"""
        ema = prices.ewm(span=period, adjust=False).mean()
        return ema.iloc[-1] if not ema.empty else None
    
    @staticmethod
    def calculate_sma(prices, period=20):
        """计算SMA指标"""
        sma = prices.rolling(window=period).mean()
        return sma.iloc[-1] if not sma.empty else None
    
    @staticmethod
    def calculate_atr(highs, lows, closes, period=14):
        """计算ATR指标"""
        tr1 = highs - lows
        tr2 = abs(highs - closes.shift(1))
        tr3 = abs(lows - closes.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.iloc[-1] if not atr.empty else None
    
    @staticmethod
    def calculate_bollinger_bands(prices, period=20, std_dev=2):
        """计算布林带指标"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return {
            "upper": upper_band.iloc[-1] if not upper_band.empty else None,
            "middle": sma.iloc[-1] if not sma.empty else None,
            "lower": lower_band.iloc[-1] if not lower_band.empty else None
        }
    
    @staticmethod
    def calculate_kdj(highs, lows, closes, period=9, k_period=3, d_period=3):
        """计算KDJ指标"""
        lowest_low = lows.rolling(window=period).min()
        highest_high = highs.rolling(window=period).max()
        rsv = (closes - lowest_low) / (highest_high - lowest_low) * 100
        k = rsv.ewm(alpha=1/k_period, adjust=False).mean()
        d = k.ewm(alpha=1/d_period, adjust=False).mean()
        j = 3 * k - 2 * d
        return {
            "k": k.iloc[-1] if not k.empty else None,
            "d": d.iloc[-1] if not d.empty else None,
            "j": j.iloc[-1] if not j.empty else None
        }
    
    @staticmethod
    def calculate_mfi(highs, lows, closes, volumes, period=14):
        """计算MFI指标"""
        typical_price = (highs + lows + closes) / 3
        money_flow = typical_price * volumes
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        mf_ratio = positive_mf / negative_mf
        mfi = 100 - (100 / (1 + mf_ratio))
        return mfi.iloc[-1] if not mfi.empty else None
    
    @staticmethod
    def calculate_adx(highs, lows, closes, period=14):
        """计算ADX趋势强度指标"""
        # 计算TR
        tr1 = highs - lows
        tr2 = abs(highs - closes.shift(1))
        tr3 = abs(lows - closes.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算DM
        high_diff = highs - highs.shift(1)
        low_diff = lows.shift(1) - lows
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # 平滑处理
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
        
        # 计算DX和ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return {
            "adx": adx.iloc[-1] if not adx.empty else None,
            "plus_di": plus_di.iloc[-1] if not plus_di.empty else None,
            "minus_di": minus_di.iloc[-1] if not minus_di.empty else None
        }
    
    @staticmethod
    def calculate_volume_analysis(volumes, closes, period=20):
        """成交量分析"""
        # 平均成交量
        avg_volume = volumes.rolling(window=period).mean()
        # 成交量比率（当前/平均）
        volume_ratio = volumes / avg_volume
        
        # 量价关系：上涨日成交量 vs 下跌日成交量
        price_change = closes.diff()
        up_volume = volumes.where(price_change > 0, 0).rolling(window=period).mean()
        down_volume = volumes.where(price_change < 0, 0).rolling(window=period).mean()
        volume_trend = up_volume / down_volume.replace(0, np.nan)
        
        return {
            "current_volume": volumes.iloc[-1] if not volumes.empty else None,
            "avg_volume": avg_volume.iloc[-1] if not avg_volume.empty else None,
            "volume_ratio": volume_ratio.iloc[-1] if not volume_ratio.empty else None,
            "volume_trend": volume_trend.iloc[-1] if not volume_trend.empty else None
        }
    
    @staticmethod
    def calculate_support_resistance(highs, lows, closes, lookback=50):
        """识别支撑阻力位"""
        if len(closes) < lookback:
            lookback = len(closes)
        
        recent_highs = highs.tail(lookback)
        recent_lows = lows.tail(lookback)
        
        # 使用局部极值点识别支撑阻力
        # 阻力位：局部高点
        resistance_levels = []
        for i in range(2, len(recent_highs) - 2):
            if recent_highs.iloc[i] >= recent_highs.iloc[i-1] and \
               recent_highs.iloc[i] >= recent_highs.iloc[i-2] and \
               recent_highs.iloc[i] >= recent_highs.iloc[i+1] and \
               recent_highs.iloc[i] >= recent_highs.iloc[i+2]:
                resistance_levels.append(recent_highs.iloc[i])
        
        # 支撑位：局部低点
        support_levels = []
        for i in range(2, len(recent_lows) - 2):
            if recent_lows.iloc[i] <= recent_lows.iloc[i-1] and \
               recent_lows.iloc[i] <= recent_lows.iloc[i-2] and \
               recent_lows.iloc[i] <= recent_lows.iloc[i+1] and \
               recent_lows.iloc[i] <= recent_lows.iloc[i+2]:
                support_levels.append(recent_lows.iloc[i])
        
        # 排序并返回最近的几个级别
        resistance_levels = sorted(list(set(resistance_levels)), reverse=True)[:3]
        support_levels = sorted(list(set(support_levels)))[:3]
        
        return {
            "resistance": resistance_levels,
            "support": support_levels
        }