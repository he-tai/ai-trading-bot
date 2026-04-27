import datetime

class RiskManager:
    def __init__(self, config):
        self.config = config
        self.daily_loss = 0
        self.consecutive_losses = 0
        self.last_reset_date = datetime.datetime.now().date()
        self.risk_limits = {
            'max_position_size': config['trading'].get('max_position_percent', 30),
            'max_daily_loss': config['risk'].get('max_daily_loss_percent', 10),
            'max_consecutive_losses': config['risk'].get('max_consecutive_losses', 5),
            'max_leverage': config['trading'].get('max_leverage', 100),
            'min_leverage': 1,
            'min_margin_level': 1.5,  # 最低保证金率
            'emergency_circuit_breaker': True,  # 紧急熔断机制
            'max_total_notional_percent': config['risk'].get('max_total_notional_percent', 60),
            'max_correlated_exposure': config['risk'].get('max_correlated_exposure_percent', 40)  # 新增：相关资产最大敞口
        }
        self.emergency_stop = False  # 紧急停止标志
        
        # 币种相关性分组（高度相关的币种）
        self.correlation_groups = [
            ['BTCUSDT', 'ETHUSDT'],  # 主流币，高度相关
            ['SOLUSDT', 'AVAXUSDT', 'MATICUSDT'],  # Layer 1
            ['BNBUSDT'],  # 交易所币（独立）
            ['DOGEUSDT', 'SHIBUSDT']  # Meme币，高度相关
        ]
    
    def reset_daily_loss(self):
        """重置每日亏损"""
        today = datetime.datetime.now().date()
        if today != self.last_reset_date:
            self.daily_loss = 0
            self.last_reset_date = today
            self.consecutive_losses = 0
            self.emergency_stop = False
    
    def check_risk(self, trade_decision, account_balance, current_positions, margin_level=None):
        """检查交易风险"""
        self.reset_daily_loss()
        
        # 检查紧急停止
        if self.emergency_stop:
            return {
                'approved': False,
                'checks': {
                    'emergency_stop': False
                },
                'reason': '系统已触发紧急停止'
            }
        
        checks = {
            'daily_loss': self.check_daily_loss(account_balance),
            'consecutive_losses': self.check_consecutive_losses(),
            'position_size': self.check_position_size(trade_decision, account_balance),
            'leverage': self.check_leverage(trade_decision),
            'concentration': self.check_concentration(trade_decision, current_positions, account_balance),
            'correlation': self.check_correlation_risk(trade_decision, current_positions, account_balance),  # 新增
            'margin_health': self.check_margin_health(margin_level)
        }
        
        # 所有检查都通过才算风险审核通过
        all_passed = all(checks.values())
        
        # 检查是否需要触发紧急熔断
        if not all_passed and self.risk_limits['emergency_circuit_breaker']:
            if not checks['daily_loss'] or not checks['margin_health']:
                self.emergency_stop = True
                return {
                    'approved': False,
                    'checks': checks,
                    'reason': '触发紧急熔断机制'
                }
        
        return {
            'approved': all_passed,
            'checks': checks
        }
    
    def check_daily_loss(self, account_balance):
        """检查每日亏损（按权益百分比）"""
        if account_balance is None or account_balance <= 0:
            return True
        daily_loss_percent = (self.daily_loss / account_balance) * 100
        return daily_loss_percent < self.risk_limits['max_daily_loss']
    
    def check_consecutive_losses(self):
        """检查连续亏损"""
        return self.consecutive_losses < self.risk_limits['max_consecutive_losses']
    
    def check_position_size(self, trade_decision, account_balance):
        """检查仓位大小"""
        position_percent = trade_decision.get('position_percent', 0)
        return position_percent <= self.risk_limits['max_position_size']
    
    def check_leverage(self, trade_decision):
        """检查杠杆"""
        leverage = trade_decision.get('leverage', 1)
        return self.risk_limits['min_leverage'] <= leverage <= self.risk_limits['max_leverage']
    
    def check_concentration(self, trade_decision, current_positions, account_balance=None):
        """检查集中度：按名义暴露（含杠杆）估算组合风险"""
        if account_balance is None or account_balance <= 0:
            return True
        # 当前持仓占总资金的比例（%）
        total_percent = sum(
            abs(pos.get('size', 0)) * pos.get('mark_price', 0) / account_balance * 100
            for pos in current_positions
        )
        new_percent = trade_decision.get('position_percent', 0) * trade_decision.get('leverage', 1)
        if total_percent + new_percent > self.risk_limits['max_total_notional_percent']:
            return False
        return True
    
    def check_margin_health(self, margin_level):
        """检查保证金健康度"""
        if margin_level is None or margin_level <= 0:
            # 无持仓时 margin_level 为 0，应允许开仓
            return True
        return margin_level > self.risk_limits['min_margin_level']
    
    def check_correlation_risk(self, trade_decision, current_positions, account_balance):
        """
        检查相关性风险：避免在同一相关组内持有过多同向仓位
        """
        if account_balance is None or account_balance <= 0:
            return True
        
        new_symbol = trade_decision.get('symbol', '')
        new_action = trade_decision.get('action', '')
        
        if not new_symbol or new_action not in ('BUY_OPEN', 'SELL_OPEN'):
            return True
        
        # 找出新交易币种所属的相关组
        new_group = None
        for group in self.correlation_groups:
            if new_symbol in group:
                new_group = group
                break
        
        if not new_group:
            return True  # 不在任何相关组中，允许
        
        # 计算该相关组内当前同向持仓的总敞口
        correlated_exposure = 0
        new_direction = 'LONG' if new_action == 'BUY_OPEN' else 'SHORT'
        
        for pos in current_positions:
            pos_symbol = pos.get('symbol', '')
            pos_direction = pos.get('direction', '')
            
            # 如果是同一相关组且同一方向
            if pos_symbol in new_group and pos_direction == new_direction:
                pos_exposure = abs(pos.get('size', 0)) * pos.get('mark_price', 0)
                correlated_exposure += pos_exposure
        
        # 加上新交易的敞口
        new_exposure = account_balance * trade_decision.get('position_percent', 0) / 100 * trade_decision.get('leverage', 1)
        total_correlated_exposure = correlated_exposure + new_exposure
        
        # 检查是否超过相关性敞口限制
        max_correlated = account_balance * self.risk_limits['max_correlated_exposure'] / 100
        
        if total_correlated_exposure > max_correlated:
            return False
        
        return True
    
    def update_loss(self, pnl):
        """更新亏损记录"""
        if pnl < 0:
            self.daily_loss += abs(pnl)
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
    
    def calculate_position_size(self, account_balance, position_percent, leverage, price):
        """计算仓位大小"""
        if price <= 0:
            return 0
        
        # 计算可用资金
        usable_balance = account_balance * (position_percent / 100)
        
        # 计算仓位大小
        position_size = (usable_balance * leverage) / price
        
        return position_size
    
    def calculate_dynamic_position_size(self, account_balance, base_position_percent, leverage, price, atr_percent, volatility_mode='normal'):
        """基于波动率的动态仓位计算"""
        if price <= 0:
            return 0, base_position_percent
        
        # 根据波动率调整仓位
        # 低波动(<0.5%): 增加仓位 20%
        # 正常波动(0.5%-2%): 基准仓位
        # 高波动(2%-4%): 减少仓位 30%
        # 极高波动(>4%): 减少仓位 50%
        
        volatility_adjustment = 1.0
        adjusted_position_percent = base_position_percent
        
        if atr_percent < 0.5:
            volatility_adjustment = 1.2
            adjusted_position_percent = min(base_position_percent * 1.2, 30)  # 最大30%
        elif atr_percent > 4:
            volatility_adjustment = 0.5
            adjusted_position_percent = base_position_percent * 0.5
        elif atr_percent > 2:
            volatility_adjustment = 0.7
            adjusted_position_percent = base_position_percent * 0.7
        
        # 计算调整后的仓位大小
        usable_balance = account_balance * (adjusted_position_percent / 100)
        position_size = (usable_balance * leverage) / price
        
        return position_size, adjusted_position_percent
    
    def adjust_position_size(self, position_size, max_position_size):
        """调整仓位大小"""
        return min(position_size, max_position_size)
    
    def get_risk_status(self):
        """获取风险状态"""
        self.reset_daily_loss()
        return {
            'daily_loss': self.daily_loss,
            'max_daily_loss': self.risk_limits['max_daily_loss'],
            'consecutive_losses': self.consecutive_losses,
            'max_consecutive_losses': self.risk_limits['max_consecutive_losses'],
            'emergency_stop': self.emergency_stop
        }