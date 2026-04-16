from data.position_data import PositionDataManager

class PositionManager:
    def __init__(self, binance_client):
        self.position_data_manager = PositionDataManager(binance_client)
        self.binance_client = binance_client
    
    def get_position(self, symbol):
        """获取特定币种的持仓信息"""
        return self.position_data_manager.get_position(symbol)
    
    def get_all_positions(self):
        """获取所有持仓信息"""
        return self.position_data_manager.get_all_positions()
    
    def has_position(self, symbol):
        """检查是否持有特定币种"""
        return self.position_data_manager.has_position(symbol)
    
    def get_position_direction(self, symbol):
        """获取持仓方向"""
        return self.position_data_manager.get_position_direction(symbol)
    
    def get_position_size(self, symbol):
        """获取持仓大小"""
        return self.position_data_manager.get_position_size(symbol)
    
    def close_position(self, symbol):
        """平仓"""
        position = self.get_position(symbol)
        if not position:
            return None
        position_amount = position.get("position_amount", 0)
        position_size = abs(position_amount)
        unrealized_pnl = position.get("unrealized_pnl", 0)
        if position_size <= 0:
            return None
        # 按交易所 LOT_SIZE 格式化数量
        try:
            lot = self.binance_client.get_symbol_lot_size(symbol)
            from decimal import Decimal
            q = Decimal(str(position_size))
            s = Decimal(str(lot["stepSize"]))
            position_size = float((q // s) * s)
        except Exception:
            pass
        side = "SELL" if position_amount > 0 else "BUY"
        position_side = position.get("position_side", "BOTH")
        try:
            order = self.binance_client.create_order(
                symbol=symbol,
                side=side,
                type_="MARKET",
                quantity=position_size,
                position_side=position_side if self.binance_client.get_position_mode() else None
            )
            print(f"平仓成功: {symbol} {side} {position_size} 盈亏: {unrealized_pnl:.2f} USDT")
            return {"order": order, "realized_pnl": unrealized_pnl}
        except Exception as e:
            print(f"平仓失败: {e}")
            return None
    
    def set_leverage(self, symbol, leverage):
        """设置杠杆"""
        try:
            result = self.binance_client.set_leverage(symbol, leverage)
            print(f"设置杠杆成功: {symbol} {leverage}x")
            return result
        except Exception as e:
            print(f"设置杠杆失败: {e}")
            return None
    
    def get_position_summary(self):
        """获取持仓摘要"""
        return self.position_data_manager.get_position_summary()