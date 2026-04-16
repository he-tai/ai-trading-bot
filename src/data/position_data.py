import time

from api.binance_client import BinanceClient

class PositionDataManager:
    def __init__(self, binance_client):
        self.binance_client = binance_client
        self.positions = {}
        self.last_update_ts = 0
        self.cache_ttl_seconds = 1.0
        self.update_positions()
    
    def update_positions(self, force=False):
        """更新持仓信息"""
        now = time.time()
        if not force and (now - self.last_update_ts) < self.cache_ttl_seconds:
            return
        try:
            position_risk = self.binance_client.get_position_risk()
            self.positions = {}
            for position in position_risk:
                # 确保position是字典类型
                if isinstance(position, dict):
                    symbol = position.get("symbol")
                    if symbol:
                        position_amount = float(position.get("positionAmt", 0))
                        if position_amount != 0:
                            pos_side = position.get("positionSide", "BOTH")
                            self.positions[symbol] = {
                                "symbol": symbol,
                                "position_amount": position_amount,
                                "position_side": pos_side,
                                "entry_price": float(position.get("entryPrice", 0)),
                                "mark_price": float(position.get("markPrice", 0)),
                                "unrealized_pnl": float(position.get("unRealizedProfit", 0)),
                                "liquidation_price": float(position.get("liquidationPrice", 0)),
                                "leverage": float(position.get("leverage", 0)),
                                "margin_type": position.get("marginType"),
                                "isolated_wallet": float(position.get("isolatedWallet", 0))
                            }
                else:
                    print(f"警告: 持仓数据格式错误，跳过: {position}")
            self.last_update_ts = now
        except Exception as e:
            print(f"更新持仓信息失败: {e}")
    
    def get_position(self, symbol):
        """获取特定币种的持仓信息"""
        self.update_positions()
        return self.positions.get(symbol)
    
    def get_all_positions(self):
        """获取所有持仓信息"""
        self.update_positions()
        return self.positions
    
    def has_position(self, symbol):
        """检查是否持有特定币种"""
        self.update_positions()
        return symbol in self.positions
    
    def get_position_direction(self, symbol):
        """获取持仓方向"""
        position = self.get_position(symbol)
        if position:
            position_amount = position.get("position_amount", 0)
            if position_amount > 0:
                return "LONG"
            elif position_amount < 0:
                return "SHORT"
        return None
    
    def get_position_size(self, symbol):
        """获取持仓大小"""
        position = self.get_position(symbol)
        if position:
            return abs(position.get("position_amount", 0))
        return 0
    
    def get_unrealized_pnl(self, symbol):
        """获取未实现盈亏"""
        position = self.get_position(symbol)
        if position:
            return position.get("unrealized_pnl", 0)
        return 0
    
    def get_position_summary(self):
        """获取持仓摘要"""
        self.update_positions()
        summary = []
        total_unrealized_pnl = 0
        for symbol, position in self.positions.items():
            total_unrealized_pnl += position.get("unrealized_pnl", 0)
            summary.append({
                "symbol": symbol,
                "direction": "LONG" if position.get("position_amount", 0) > 0 else "SHORT",
                "size": abs(position.get("position_amount", 0)),
                "entry_price": position.get("entry_price", 0),
                "mark_price": position.get("mark_price", 0),
                "unrealized_pnl": position.get("unrealized_pnl", 0),
                "leverage": position.get("leverage", 0)
            })
        
        return {
            "positions": summary,
            "total_unrealized_pnl": total_unrealized_pnl,
            "position_count": len(summary)
        }
    
    def calculate_pnl_percent(self, symbol):
        """计算盈亏百分比"""
        position = self.get_position(symbol)
        if position:
            entry_price = position.get("entry_price", 0)
            mark_price = position.get("mark_price", 0)
            if entry_price > 0:
                if position.get("position_amount", 0) > 0:
                    # LONG 仓位
                    return ((mark_price - entry_price) / entry_price) * 100
                else:
                    # SHORT 仓位
                    return ((entry_price - mark_price) / entry_price) * 100
        return 0