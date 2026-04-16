import json
import os

class ConfigLoader:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """加载交易配置"""
        config_path = os.path.join(self.config_dir, "trading_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.validate_config()
        else:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

    def validate_config(self):
        """基础配置校验（生产必需）"""
        required_sections = ["trading", "risk", "ai", "schedule"]
        for section in required_sections:
            if section not in self.config or not isinstance(self.config.get(section), dict):
                raise ValueError(f"配置缺少必要段: {section}")

        trading = self.config["trading"]
        risk = self.config["risk"]
        ai = self.config["ai"]
        schedule = self.config["schedule"]

        symbols = trading.get("symbols", [])
        if not isinstance(symbols, list) or not symbols:
            raise ValueError("trading.symbols 必须是非空数组")
        for sym in symbols:
            if not isinstance(sym, str) or not sym.endswith("USDT"):
                raise ValueError(f"无效交易对: {sym}，应为类似 BTCUSDT")

        self._ensure_range(trading, "default_leverage", 1, 125)
        self._ensure_range(trading, "max_leverage", 1, 125)
        if trading.get("default_leverage", 1) > trading.get("max_leverage", 1):
            raise ValueError("trading.default_leverage 不能大于 trading.max_leverage")
        self._ensure_range(trading, "min_position_percent", 0, 100)
        self._ensure_range(trading, "max_position_percent", 0, 100)
        if trading.get("min_position_percent", 0) > trading.get("max_position_percent", 0):
            raise ValueError("trading.min_position_percent 不能大于 trading.max_position_percent")
        self._ensure_range(trading, "reserve_percent", 0, 100)

        self._ensure_range(risk, "max_daily_loss_percent", 0.1, 100)
        self._ensure_range(risk, "max_consecutive_losses", 1, 100, integer=True)
        self._ensure_range(risk, "stop_loss_default_percent", 0.1, 50)
        self._ensure_range(risk, "take_profit_default_percent", 0.1, 100)
        if "min_confidence_to_open" in risk:
            self._ensure_range(risk, "min_confidence_to_open", 0, 1)
        if "max_total_notional_percent" in risk:
            self._ensure_range(risk, "max_total_notional_percent", 1, 1000)

        self._ensure_range(ai, "temperature", 0, 1)
        self._ensure_range(ai, "max_tokens", 100, 32000, integer=True)
        if "timeout_seconds" in ai:
            self._ensure_range(ai, "timeout_seconds", 5, 3600, integer=True)

        self._ensure_range(schedule, "interval_seconds", 10, 86400, integer=True)
        if "retry_times" in schedule:
            self._ensure_range(schedule, "retry_times", 0, 50, integer=True)
        if "retry_delay_seconds" in schedule:
            self._ensure_range(schedule, "retry_delay_seconds", 0, 3600, integer=True)

    def _ensure_range(self, obj, key, min_v, max_v, integer=False):
        if key not in obj:
            raise ValueError(f"缺少必要配置: {key}")
        val = obj.get(key)
        try:
            num = int(val) if integer else float(val)
        except (TypeError, ValueError):
            raise ValueError(f"配置 {key} 类型错误: {val}") from None
        if num < min_v or num > max_v:
            raise ValueError(f"配置 {key} 越界: {num}，应在 [{min_v}, {max_v}]")
    
    def get(self, key, default=None):
        """获取配置值"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_trading_config(self):
        """获取交易配置"""
        return self.config.get("trading", {})
    
    def get_risk_config(self):
        """获取风险配置"""
        return self.config.get("risk", {})
    
    def get_ai_config(self):
        """获取AI配置"""
        return self.config.get("ai", {})
    
    def get_schedule_config(self):
        """获取调度配置"""
        return self.config.get("schedule", {})