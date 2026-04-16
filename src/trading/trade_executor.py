import time
from decimal import Decimal
from api.binance_client import BinanceClient

class TradeExecutor:
    def __init__(self, binance_client, position_manager, risk_manager):
        self.binance_client = binance_client
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        self.retry_times = 3
        self.retry_delay = 5
    
    def execute_trade(self, symbol, trade_decision, account_balance):
        """执行交易"""
        action = trade_decision.get('action')
        leverage = trade_decision.get('leverage', 3)
        position_percent = trade_decision.get('position_percent', 0)
        take_profit = trade_decision.get('take_profit_percent', 5)
        stop_loss = trade_decision.get('stop_loss_percent', -2)
        if action in ('BUY_OPEN', 'SELL_OPEN') and (not isinstance(stop_loss, (int, float)) or stop_loss >= 0):
            print(f"{symbol} 止损参数无效，拒绝开仓")
            return None
        
        # 设置杠杆
        self.position_manager.set_leverage(symbol, leverage)
        
        # 根据动作执行不同的交易
        if action == 'BUY_OPEN':
            return self.open_long_position(symbol, position_percent, account_balance, leverage, take_profit, stop_loss)
        elif action == 'SELL_OPEN':
            return self.open_short_position(symbol, position_percent, account_balance, leverage, take_profit, stop_loss)
        elif action == 'CLOSE':
            return self.close_position(symbol)
        elif action == 'HOLD':
            print(f"持有 {symbol}，不执行交易")
            return None
        else:
            print(f"未知动作: {action}")
            return None
    
    def open_long_position(self, symbol, position_percent, account_balance, leverage, take_profit, stop_loss):
        """开多仓"""
        # 计算仓位大小（考虑杠杆）
        position_size = self.calculate_position_size(symbol, position_percent, account_balance, leverage)
        if position_size <= 0:
            try:
                lot = self.binance_client.get_symbol_lot_size(symbol)
                price = float(self.binance_client.get_ticker(symbol).get("lastPrice", 0) or 0)
                min_usdt = lot["minQty"] * price if price else 0
                print(f"仓位大小计算失败: {symbol} (最小{lot['minQty']}，约{min_usdt:.0f} USDT。可提高仓位比例或改用ETH/SOL)")
            except Exception:
                print(f"仓位大小计算失败: {symbol} (可能低于交易所最小数量)")
            return None
        
        # 执行开仓
        try:
            pos_side = "LONG" if self.binance_client.get_position_mode() else None
            open_order = self.binance_client.create_order(
                symbol=symbol,
                side='BUY',
                type_='MARKET',
                quantity=position_size,
                position_side=pos_side
            )
            print(f"开多成功: {symbol} {position_size} @ 市价")
            
            # 获取开仓价：优先用持仓均价（加仓时正确），其次订单成交价，最后最新价
            position = self.position_manager.get_position(symbol)
            entry_price = float(position.get('entry_price', 0) or 0) if position else 0
            if entry_price <= 0:
                entry_price = float(open_order.get('avgPrice', 0) or 0)
            if entry_price <= 0:
                entry_price = float(self.binance_client.get_ticker(symbol).get('lastPrice', 0) or 0)
            
            # 总持仓量（可能加仓，需覆盖全部）
            total_size = self.position_manager.get_position_size(symbol) or position_size
            total_size = max(total_size, position_size)
            total_size = self.adjust_position_size(symbol, total_size)
            
            # 取消该币种已有止盈止损，避免重复或数量不一致
            self._cancel_tp_sl_orders(symbol)
            # 设置止盈止损（使用 STOP_MARKET/TAKE_PROFIT_MARKET，触发后市价成交更可靠）
            if take_profit > 0 and total_size > 0:
                tp_price = entry_price * (1 + take_profit / 100)
                self.set_take_profit(symbol, 'SELL', tp_price, total_size, pos_side)
            if stop_loss < 0 and total_size > 0:
                sl_price = entry_price * (1 + stop_loss / 100)
                self.set_stop_loss(symbol, 'SELL', sl_price, total_size, pos_side)
            
            return open_order
        except Exception as e:
            print(f"开多失败: {e}")
            return None
    
    def open_short_position(self, symbol, position_percent, account_balance, leverage, take_profit, stop_loss):
        """开空仓"""
        # 计算仓位大小（考虑杠杆）
        position_size = self.calculate_position_size(symbol, position_percent, account_balance, leverage)
        if position_size <= 0:
            try:
                lot = self.binance_client.get_symbol_lot_size(symbol)
                price = float(self.binance_client.get_ticker(symbol).get("lastPrice", 0) or 0)
                min_usdt = lot["minQty"] * price if price else 0
                print(f"仓位大小计算失败: {symbol} (最小{lot['minQty']}，约{min_usdt:.0f} USDT。可提高仓位比例或改用ETH/SOL)")
            except Exception:
                print(f"仓位大小计算失败: {symbol} (可能低于交易所最小数量)")
            return None
        
        # 执行开仓
        try:
            pos_side = "SHORT" if self.binance_client.get_position_mode() else None
            open_order = self.binance_client.create_order(
                symbol=symbol,
                side='SELL',
                type_='MARKET',
                quantity=position_size,
                position_side=pos_side
            )
            print(f"开空成功: {symbol} {position_size} @ 市价")
            
            # 获取开仓价：优先用持仓均价（加仓时正确），其次订单成交价，最后最新价
            position = self.position_manager.get_position(symbol)
            entry_price = float(position.get('entry_price', 0) or 0) if position else 0
            if entry_price <= 0:
                entry_price = float(open_order.get('avgPrice', 0) or 0)
            if entry_price <= 0:
                entry_price = float(self.binance_client.get_ticker(symbol).get('lastPrice', 0) or 0)
            
            # 总持仓量（可能加仓，需覆盖全部）
            total_size = self.position_manager.get_position_size(symbol) or position_size
            total_size = max(total_size, position_size)
            total_size = self.adjust_position_size(symbol, total_size)
            
            # 取消该币种已有止盈止损，避免重复或数量不一致
            self._cancel_tp_sl_orders(symbol)
            # 设置止盈止损（使用 STOP_MARKET/TAKE_PROFIT_MARKET，触发后市价成交更可靠）
            if take_profit > 0 and total_size > 0:
                tp_price = entry_price * (1 - take_profit / 100)
                self.set_take_profit(symbol, 'BUY', tp_price, total_size, pos_side)
            if stop_loss < 0 and total_size > 0:
                sl_price = entry_price * (1 - stop_loss / 100)
                self.set_stop_loss(symbol, 'BUY', sl_price, total_size, pos_side)
            
            return open_order
        except Exception as e:
            print(f"开空失败: {e}")
            return None
    
    def close_position(self, symbol):
        """平仓"""
        result = self.position_manager.close_position(symbol)
        if result and "realized_pnl" in result:
            self.risk_manager.update_loss(result["realized_pnl"])
        return result.get("order", result) if result else None
    
    def _cancel_tp_sl_orders(self, symbol):
        """取消该币种所有未成交订单（含止盈止损），避免重复挂单"""
        try:
            r = self.binance_client.cancel_all_open_orders(symbol)
            if isinstance(r, dict) and r.get("code") not in (0, None, 200):
                return  # API 返回非成功码（如无订单可取消）时静默
            print(f"已取消 {symbol} 已有止盈止损订单")
            time.sleep(0.3)  # 等待交易所处理
        except Exception as e:
            print(f"取消 {symbol} 已有订单时忽略: {e}")

    def set_take_profit(self, symbol, side, price, quantity, position_side=None):
        """设置止盈。使用 TAKE_PROFIT_MARKET，触发后市价成交，避免 LIMIT 触发后不成交"""
        try:
            ps = position_side if self.binance_client.get_position_mode() else None
            order = self.binance_client.create_order(
                symbol=symbol,
                side=side,
                type_='TAKE_PROFIT_MARKET',
                quantity=quantity,
                stop_price=price,
                position_side=ps
            )
            print(f"设置止盈成功: {symbol} {side} {quantity} @ {price}")
            return order
        except Exception as e:
            print(f"设置止盈失败: {e}")
            return None

    def set_stop_loss(self, symbol, side, price, quantity, position_side=None):
        """设置止损。使用 STOP_MARKET，触发后市价成交，避免 LIMIT 价格滑点导致不成交"""
        try:
            ps = position_side if self.binance_client.get_position_mode() else None
            order = self.binance_client.create_order(
                symbol=symbol,
                side=side,
                type_='STOP_MARKET',
                quantity=quantity,
                stop_price=price,
                position_side=ps
            )
            print(f"设置止损成功: {symbol} {side} {quantity} @ {price}")
            return order
        except Exception as e:
            print(f"设置止损失败: {e}")
            return None
    
    def calculate_position_size(self, symbol, position_percent, account_balance, leverage=1):
        """计算仓位大小"""
        if position_percent <= 0:
            return 0
        
        # 获取当前价格
        try:
            ticker_data = self.binance_client.get_ticker(symbol)
            price = float(ticker_data.get('lastPrice', 0))
            if price <= 0:
                return 0
            
            # 可用保证金 = 总资金 * 仓位比例
            margin = account_balance * (position_percent / 100)
            # 仓位名义价值 = 保证金 * 杠杆，数量 = 名义价值 / 价格
            position_size = (margin * leverage) / price
            
            # 按交易所 LOT_SIZE 规则调整，并确保 >= minQty
            position_size = self.adjust_position_size(symbol, position_size)
            
            return position_size
        except Exception as e:
            print(f"计算仓位大小失败: {e}")
            return 0
    
    def adjust_position_size(self, symbol, position_size):
        """按交易所 LOT_SIZE 规则调整数量（stepSize、minQty）"""
        try:
            lot = self.binance_client.get_symbol_lot_size(symbol)
            min_qty = lot["minQty"]
            step = lot["stepSize"]
            if position_size < min_qty:
                return 0
            # 向下取整到 stepSize 的整数倍（避免浮点误差）
            q = Decimal(str(position_size))
            s = Decimal(str(step))
            adjusted = (q // s) * s
            result = float(adjusted)
            return result if result >= min_qty else 0
        except Exception as e:
            print(f"调整仓位精度失败: {e}")
            # 兜底：BTC 3位，其他 2位
            step = 0.001 if "BTC" in symbol else 0.01
            return max(step, round(position_size, 3 if "BTC" in symbol else 2))
    
    def retry_execution(self, func, *args, **kwargs):
        """重试执行"""
        for i in range(self.retry_times):
            try:
                result = func(*args, **kwargs)
                if result:
                    return result
            except Exception as e:
                print(f"执行失败 ({i+1}/{self.retry_times}): {e}")
            time.sleep(self.retry_delay)
        return None