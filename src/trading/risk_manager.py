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
            'max_total_notional_percent': config['risk'].get('max_total_notional_percent', 60)
        }
        self.emergency_stop = False  # 紧急停止标志
    
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