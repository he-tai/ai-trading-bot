from api.binance_client import BinanceClient

class AccountDataManager:
    def __init__(self, binance_client):
        self.binance_client = binance_client
        self.account_info = None
        self.update_account_info()
    
    def update_account_info(self):
        """更新账户信息"""
        try:
            self.account_info = self.binance_client.get_account()
        except Exception as e:
            print(f"更新账户信息失败: {e}")
    
    def get_total_balance(self):
        """获取总权益"""
        if self.account_info:
            return float(self.account_info.get("totalWalletBalance", 0))
        return 0
    
    def get_available_balance(self):
        """获取可用资金"""
        if self.account_info:
            return float(self.account_info.get("availableBalance", 0))
        return 0
    
    def get_margin_balance(self):
        """获取保证金余额"""
        if self.account_info:
            return float(self.account_info.get("totalMarginBalance", 0))
        return 0
    
    def get_unrealized_pnl(self):
        """获取未实现盈亏"""
        if self.account_info:
            return float(self.account_info.get("totalUnrealizedProfit", 0))
        return 0
    
    def get_margin_level(self):
        """获取保证金率"""
        if self.account_info:
            return float(self.account_info.get("totalMarginLevel", 0))
        return 0
    
    def get_account_summary(self):
        """获取账户摘要"""
        self.update_account_info()
        return {
            "total_balance": self.get_total_balance(),
            "available_balance": self.get_available_balance(),
            "margin_balance": self.get_margin_balance(),
            "unrealized_pnl": self.get_unrealized_pnl(),
            "margin_level": self.get_margin_level()
        }
    
    def calculate_position_size(self, symbol, percent, leverage):
        """计算仓位大小"""
        total_balance = self.get_total_balance()
        available_balance = self.get_available_balance()
        
        # 计算可用资金比例
        usable_balance = available_balance * (percent / 100)
        
        # 获取当前价格
        ticker_data = self.binance_client.get_ticker(symbol)
        price = float(ticker_data.get("lastPrice", 0))
        
        if price > 0:
            # 计算仓位大小
            position_size = (usable_balance * leverage) / price
            return position_size
        return 0
    
    def check_daily_loss(self, daily_loss_limit):
        """检查每日亏损是否超过限制"""
        # 实现每日亏损检查逻辑
        # 这里需要存储每日初始余额，并计算当前亏损比例
        pass