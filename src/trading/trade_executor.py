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
        # 移动止损配置
        self.trailing_stop_config = {
            'activation_percent': 1.0,  # 盈利1%后激活移动止损
            'trail_percent': 0.5,       # 回撤0.5%触发止损
            'min_trail_amount': 0.1     # 最小移动距离(防止频繁调整)
        }
        # 分批止盈配置
        self.partial_tp_config = {
            'enabled': True,
            'levels': [
                {'percent': 50, 'target_percent': 1.5},  # 50%仓位在1.5%止盈
                {'percent': 30, 'target_percent': 3.0},  # 30%仓位在3.0%止盈
                {'percent': 20, 'target_percent': 5.0}   # 20%仓位在5.0%止盈
            ]
        }
    
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
            
            # 设置止盈止损：支持分批止盈或单一止盈
            risk_config = self.risk_manager.config.get('risk', {})
            enable_partial_tp = risk_config.get('enable_partial_take_profit', False)
            
            if enable_partial_tp:
                # 分批止盈
                self._set_partial_take_profits(symbol, 'SELL', entry_price, total_size, pos_side, risk_config)
            else:
                # 单一止盈（原逻轼）
                if take_profit > 0 and total_size > 0:
                    tp_price = entry_price * (1 + take_profit / 100)
                    self.set_take_profit(symbol, 'SELL', tp_price, total_size, pos_side)
            
            # 止损始终使用全部仓位
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
            
            # 设置止盈止损：支持分批止盈或单一止盈
            risk_config = self.risk_manager.config.get('risk', {})
            enable_partial_tp = risk_config.get('enable_partial_take_profit', False)
            
            if enable_partial_tp:
                # 分批止盈
                self._set_partial_take_profits(symbol, 'BUY', entry_price, total_size, pos_side, risk_config)
            else:
                # 单一止盈（原逻轼）
                if take_profit > 0 and total_size > 0:
                    tp_price = entry_price * (1 - take_profit / 100)
                    self.set_take_profit(symbol, 'BUY', tp_price, total_size, pos_side)
            
            # 止损始终使用全部仓位
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
    
    def _set_partial_take_profits(self, symbol, side, entry_price, total_size, position_side, risk_config):
        """
        设置分批止盈订单
        :param symbol: 交易对
        :param side: SELL(多头止盈) 或 BUY(空头止盈)
        :param entry_price: 入场价格
        :param total_size: 总持仓量
        :param position_side: LONG 或 SHORT
        :param risk_config: 风险配置
        """
        if total_size <= 0:
            return
        
        partial_levels = risk_config.get('partial_tp_levels', self.partial_tp_config['levels'])
        
        remaining_size = total_size
        for i, level in enumerate(partial_levels):
            # 计算该级别的仓位大小
            level_percent = level['percent'] / 100
            if i == len(partial_levels) - 1:
                # 最后一级使用剩余全部仓位（避免精度损失）
                level_size = remaining_size
            else:
                level_size = total_size * level_percent
                level_size = self.adjust_position_size(symbol, level_size)
            
            if level_size <= 0:
                continue
            
            # 计算止盈价格
            target_percent = level['target_percent']
            if side == 'SELL':  # 多头止盈
                tp_price = entry_price * (1 + target_percent / 100)
            else:  # 空头止盈
                tp_price = entry_price * (1 - target_percent / 100)
            
            # 设置止盈订单
            self.set_take_profit(symbol, side, tp_price, level_size, position_side)
            
            remaining_size -= level_size
            print(f"分批止盈 {i+1}: {level_size:.6f} @ {tp_price:.2f} ({target_percent}%)")

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
    
    def update_trailing_stop(self, symbol, position, entry_price, current_price, side):
        """
        更新移动止损
        :param symbol: 交易对
        :param position: 持仓信息
        :param entry_price: 入场价格
        :param current_price: 当前价格
        :param side: SELL(多头) 或 BUY(空头)
        :return: 新的止损价格，如果不需要调整则返回None
        """
        try:
            # 计算盈利百分比
            if side == 'SELL':  # 多头持仓
                profit_percent = ((current_price - entry_price) / entry_price) * 100
            else:  # 空头持仓
                profit_percent = ((entry_price - current_price) / entry_price) * 100
            
            # 检查是否达到激活阈值
            if profit_percent < self.trailing_stop_config['activation_percent']:
                return None
            
            # 计算新的止损价格
            if side == 'SELL':  # 多头：止损价格跟随价格上涨
                new_stop_price = current_price * (1 - self.trailing_stop_config['trail_percent'] / 100)
                # 确保新止损价格高于当前止损价格（只上移不下移）
                current_stop = position.get('stop_loss_price', 0)
                if current_stop and new_stop_price <= current_stop + self.trailing_stop_config['min_trail_amount']:
                    return None  # 不需要调整
                return new_stop_price
            else:  # 空头：止损价格跟随价格下跌
                new_stop_price = current_price * (1 + self.trailing_stop_config['trail_percent'] / 100)
                current_stop = position.get('stop_loss_price', 0)
                if current_stop and new_stop_price >= current_stop - self.trailing_stop_config['min_trail_amount']:
                    return None  # 不需要调整
                return new_stop_price
        except Exception as e:
            print(f"计算移动止损失败: {e}")
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