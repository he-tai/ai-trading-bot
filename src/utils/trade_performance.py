"""交易表现跟踪和反馈系统"""
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

class TradePerformanceTracker:
    """跟踪交易表现并为AI决策提供反馈"""
    
    def __init__(self, log_file='logs/trade_history.json'):
        self.log_file = log_file
        self.trade_history = self._load_history()
        
    def _load_history(self):
        """加载历史交易记录"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self):
        """保存交易历史"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w') as f:
            json.dump(self.trade_history, f, indent=2)
    
    def record_trade(self, symbol, action, entry_price, exit_price=None, 
                    position_size=0, pnl=0, confidence=0.5, 
                    market_conditions=None, ai_reason=''):
        """记录交易"""
        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': action,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'position_size': position_size,
            'pnl': pnl,
            'confidence': confidence,
            'market_conditions': market_conditions or {},
            'ai_reason': ai_reason,
            'status': 'closed' if exit_price else 'open'
        }
        self.trade_history.append(trade)
        self._save_history()
    
    def get_performance_stats(self, days=30):
        """获取最近的交易统计数据"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_trades = [
            t for t in self.trade_history 
            if datetime.fromisoformat(t['timestamp']) > cutoff_date and t['status'] == 'closed'
        ]
        
        if not recent_trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0,
                'total_pnl': 0,
                'avg_confidence': 0,
                'confidence_accuracy': 0
            }
        
        winning_trades = [t for t in recent_trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(recent_trades) if recent_trades else 0
        
        total_pnl = sum(t['pnl'] for t in recent_trades)
        avg_pnl = total_pnl / len(recent_trades) if recent_trades else 0
        
        avg_confidence = sum(t['confidence'] for t in recent_trades) / len(recent_trades)
        
        # 置信度准确性：高置信度交易是否真的更可能盈利
        high_conf_trades = [t for t in recent_trades if t['confidence'] >= 0.7]
        low_conf_trades = [t for t in recent_trades if t['confidence'] < 0.7]
        
        high_conf_win_rate = len([t for t in high_conf_trades if t['pnl'] > 0]) / len(high_conf_trades) if high_conf_trades else 0
        low_conf_win_rate = len([t for t in low_conf_trades if t['pnl'] > 0]) / len(low_conf_trades) if low_conf_trades else 0
        
        confidence_accuracy = high_conf_win_rate - low_conf_win_rate
        
        return {
            'total_trades': len(recent_trades),
            'win_rate': round(win_rate, 3),
            'avg_pnl': round(avg_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_confidence': round(avg_confidence, 3),
            'confidence_accuracy': round(confidence_accuracy, 3),
            'high_conf_win_rate': round(high_conf_win_rate, 3),
            'low_conf_win_rate': round(low_conf_win_rate, 3)
        }
    
    def get_symbol_performance(self, symbol, days=30):
        """获取特定币种的表现"""
        cutoff_date = datetime.now() - timedelta(days=days)
        symbol_trades = [
            t for t in self.trade_history 
            if t['symbol'] == symbol and 
            datetime.fromisoformat(t['timestamp']) > cutoff_date and 
            t['status'] == 'closed'
        ]
        
        if not symbol_trades:
            return None
        
        winning = [t for t in symbol_trades if t['pnl'] > 0]
        win_rate = len(winning) / len(symbol_trades)
        total_pnl = sum(t['pnl'] for t in symbol_trades)
        
        return {
            'total_trades': len(symbol_trades),
            'win_rate': round(win_rate, 3),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(total_pnl / len(symbol_trades), 2)
        }
    
    def get_feedback_for_ai(self, days=30):
        """生成给AI的反馈信息"""
        stats = self.get_performance_stats(days)
        
        if stats['total_trades'] == 0:
            return "暂无历史交易数据，请基于技术分析做出决策。"
        
        feedback = []
        feedback.append(f"过去{days}天交易表现:")
        feedback.append(f"- 总交易次数: {stats['total_trades']}")
        feedback.append(f"- 胜率: {stats['win_rate']*100:.1f}%")
        feedback.append(f"- 平均盈亏: {stats['avg_pnl']:.2f} USDT")
        feedback.append(f"- 总盈亏: {stats['total_pnl']:.2f} USDT")
        
        if stats['confidence_accuracy'] > 0.1:
            feedback.append("- 你的高置信度决策表现更好，请继续保持谨慎态度")
        elif stats['confidence_accuracy'] < -0.1:
            feedback.append("- 注意：你的高置信度决策表现不如预期，请重新评估决策标准")
        
        # 按币种分析
        symbols = set(t['symbol'] for t in self.trade_history if t['status'] == 'closed')
        for symbol in symbols:
            sym_stats = self.get_symbol_performance(symbol, days)
            if sym_stats and sym_stats['total_trades'] >= 3:
                feedback.append(f"- {symbol}: 胜率{sym_stats['win_rate']*100:.1f}%, 总盈亏{sym_stats['total_pnl']:.2f} USDT")
        
        return "\n".join(feedback)
    
    def get_recent_trades(self, limit=10):
        """获取最近的交易"""
        return self.trade_history[-limit:]
