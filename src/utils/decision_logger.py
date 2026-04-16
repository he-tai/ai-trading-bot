"""决策日志：记录每轮 AI 决策的完整上下文与执行结果"""
import os
import json
import time
from datetime import datetime


class DecisionLogger:
    """将决策详情写入独立日志文件，便于复盘与分析"""

    def __init__(self, log_path=None):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.log_path = log_path or os.path.join(project_root, "logs", "decisions.log")
        self._ensure_dir()

    def _ensure_dir(self):
        d = os.path.dirname(self.log_path)
        if d:
            os.makedirs(d, exist_ok=True)

    def _write(self, content):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(content)
                f.flush()
        except (IOError, OSError) as e:
            print(f"决策日志写入失败: {e}")

    def log_cycle_start(self, cycle, account_summary, position_summary, sentiment_summary=None):
        """记录周期开始：账户、持仓、情绪"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "",
            "=" * 70,
            f"[{ts}] 交易周期 #{cycle} 开始",
            "=" * 70,
            "【账户】",
            f"  总权益: {account_summary['total_balance']:.2f} USDT",
            f"  可用: {account_summary['available_balance']:.2f} USDT",
            f"  未实现盈亏: {account_summary['unrealized_pnl']:.2f} USDT",
            f"  保证金率: {account_summary['margin_level']:.2f}%",
            "【持仓】",
        ]
        if position_summary.get("positions"):
            for p in position_summary["positions"]:
                lines.append(f"  {p['symbol']}: {p['direction']} {p['size']:.4f} @ {p['entry_price']:.2f} | 盈亏: {p['unrealized_pnl']:.2f} USDT")
        else:
            lines.append("  无持仓")
        if sentiment_summary:
            fng = sentiment_summary.get("fear_greed")
            if fng:
                lines.append(f"【情绪】恐惧贪婪: {fng['value']} ({fng['classification']})")
            na = sentiment_summary.get("news_analysis")
            if na and na.get("strategy_hints"):
                h = na["strategy_hints"]
                lines.append(
                    f"【新闻闸门】risk_off={h.get('risk_off')} | macro≈{h.get('macro_stress_hits')} | hack≈{h.get('hack_hits')}"
                )
        lines.append("")
        self._write("\n".join(lines))

    def log_market_summary(self, market_analyses):
        """记录市场数据摘要（价格、24h涨跌、资金费率）"""
        lines = ["【市场摘要】"]
        for symbol, a in market_analyses.items():
            lines.append(f"  {symbol}: ${a['price']:.2f} | 24h: {a['24h_change']:.2f}% | 费率: {a['funding_rate']:.6f}")
        lines.append("")
        self._write("\n".join(lines))

    def log_ai_decision(self, decision, raw_text_preview=None):
        """记录 AI 决策详情"""
        lines = ["【AI 决策】"]
        for symbol, d in decision.items():
            lines.append(f"  {symbol}:")
            lines.append(f"    动作: {d.get('action', 'HOLD')}")
            lines.append(f"    理由: {d.get('reason', '')}")
            lines.append(f"    置信度: {d.get('confidence', 0):.2f} | 杠杆: {d.get('leverage', 0)}x | 仓位: {d.get('position_percent', 0)}%")
            lines.append(f"    止盈: {d.get('take_profit_percent', 0)}% | 止损: {d.get('stop_loss_percent', 0)}%")
        if raw_text_preview:
            lines.append(f"  [原始返回预览] {raw_text_preview[:300]}...")
        lines.append("")
        self._write("\n".join(lines))

    def log_decision_parse_fail(self, raw_text, error_msg):
        """记录决策解析失败"""
        lines = [
            "【AI 决策解析失败】",
            f"  错误: {error_msg}",
            f"  原始返回: {raw_text[:500]}..." if raw_text and len(raw_text) > 500 else f"  原始返回: {raw_text or '(空)'}",
            "",
        ]
        self._write("\n".join(lines))

    def log_execution(self, symbol, action, risk_approved, risk_failed=None, order_success=None, order_error=None):
        """记录单笔执行结果"""
        status = "通过" if risk_approved else "拒绝"
        risk_info = f"风险检查: {status}"
        if risk_failed:
            risk_info += f" (未通过: {risk_failed})"
        exec_info = ""
        if risk_approved:
            if order_success is True:
                exec_info = " | 下单: 成功"
            elif order_success is False:
                exec_info = f" | 下单: 失败 ({order_error or '未知'})"
        lines = [f"  【执行】{symbol} {action} | {risk_info}{exec_info}"]
        self._write("\n".join(lines) + "\n")

    def log_cycle_end(self, cycle, has_trade=False):
        """记录周期结束"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action = "有交易执行" if has_trade else "无交易"
        self._write(f"[{ts}] 周期 #{cycle} 结束 ({action})\n")
