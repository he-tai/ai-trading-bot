import json

class PromptBuilder:
    def __init__(self):
        pass
    
    def build_prompt(self, market_analyses, account_summary, position_summary, config, sentiment_summary=None, performance_feedback=None):
        """构建完整的提示词。sentiment_summary 可选，含恐惧贪婪指数、新闻等。performance_feedback 为历史表现反馈"""
        prompt_parts = []
        
        # 添加情绪与新闻（若有）
        if sentiment_summary:
            prompt_parts.append("# 市场情绪与新闻")
            fng = sentiment_summary.get("fear_greed")
            if fng:
                prompt_parts.append(f"恐惧贪婪指数: {fng['value']} ({fng['classification']})")
                prompt_parts.append("  (0=极度恐惧, 100=极度贪婪, 可作为逆向或顺势参考)")
            news = sentiment_summary.get("news")
            if news:
                prompt_parts.append("\n近期热点新闻:")
                for i, n in enumerate(news[:5], 1):
                    votes = f"👍{n.get('positive',0)} 👎{n.get('negative',0)}"
                    source = n.get("source", "")
                    source_text = f" | 来源: {source}" if source else ""
                    prompt_parts.append(f"  {i}. {n.get('title', '')[:80]}... [{votes}{source_text}]")
            news_analysis = sentiment_summary.get("news_analysis")
            if news_analysis:
                prompt_parts.append("\nRSS新闻分析摘要:")
                prompt_parts.append(f"  总新闻数: {news_analysis.get('total_news', 0)}")
                top_keywords = news_analysis.get("top_keywords", [])
                if top_keywords:
                    top_text = ", ".join([f"{k}:{v}" for k, v in top_keywords])
                    prompt_parts.append(f"  关键词热度: {top_text}")
                hints = news_analysis.get("strategy_hints")
                if hints:
                    prompt_parts.append(
                        f"  系统新闻闸门: risk_off={hints.get('risk_off')} | "
                        f"宏观监管类标题计数≈{hints.get('macro_stress_hits')} | "
                        f"安全类≈{hints.get('hack_hits')}"
                    )
                    # 新增：情感分析结果
                    sentiment_score = hints.get('sentiment_score', 0)
                    sentiment_class = hints.get('sentiment_classification', 'neutral')
                    prompt_parts.append(f"  新闻情感评分: {sentiment_score} ({sentiment_class})")
                    prompt_parts.append(
                        "  (说明: 程序可能据此暂停新开仓或提高开仓置信度阈值，请与技术面综合判断)"
                    )
            prompt_parts.append("")
        
        # 添加账户信息
        prompt_parts.append("# 账户信息")
        prompt_parts.append(f"总权益: {account_summary['total_balance']:.2f} USDT")
        prompt_parts.append(f"可用资金: {account_summary['available_balance']:.2f} USDT")
        prompt_parts.append(f"未实现盈亏: {account_summary['unrealized_pnl']:.2f} USDT")
        prompt_parts.append(f"保证金率: {account_summary['margin_level']:.2f}%")
        prompt_parts.append("")
        
        # 添加持仓信息
        if position_summary['positions']:
            prompt_parts.append("# 持仓信息")
            for position in position_summary['positions']:
                prompt_parts.append(f"{position['symbol']}: {position['direction']} {position['size']:.4f} @ {position['entry_price']:.2f}")
                prompt_parts.append(f"  当前价格: {position['mark_price']:.2f}")
                prompt_parts.append(f"  未实现盈亏: {position['unrealized_pnl']:.2f} USDT")
                prompt_parts.append(f"  杠杆: {position['leverage']}x")
            prompt_parts.append("")
        else:
            prompt_parts.append("# 持仓信息")
            prompt_parts.append("当前无持仓")
            prompt_parts.append("")
        
        # 添加市场分析
        prompt_parts.append("# 市场分析")
        for symbol, analysis in market_analyses.items():
            prompt_parts.append(f"## {symbol}")
            prompt_parts.append(f"价格: ${analysis['price']:.2f} | 24h: {analysis['24h_change']:.2f}% | 资金费率: {analysis['funding_rate']:.6f}")
            
            # 添加多周期技术指标（处理 None 值）
            def _fmt(v, fmt_str):
                return fmt_str.format(v) if v is not None else "N/A"
            for interval, data in analysis['market_data'].items():
                ind = data['indicators']
                prompt_parts.append(f"\n【{interval}周期】")
                prompt_parts.append(f"RSI: {_fmt(ind.get('rsi'), '{:.1f}')}")
                macd = ind.get('macd') or {}
                prompt_parts.append(f"MACD: {_fmt(macd.get('macd'), '{:.4f}')} | Signal: {_fmt(macd.get('signal'), '{:.4f}')} | Histogram: {_fmt(macd.get('histogram'), '{:.4f}')}")
                prompt_parts.append(f"EMA20: {_fmt(ind.get('ema20'), '{:.2f}')} | EMA50: {_fmt(ind.get('ema50'), '{:.2f}')}")
                prompt_parts.append(f"ATR: {_fmt(ind.get('atr'), '{:.2f}')}")
                bb = ind.get('bollinger_bands') or {}
                prompt_parts.append(f"布林带: 上轨 {_fmt(bb.get('upper'), '{:.2f}')} | 中轨 {_fmt(bb.get('middle'), '{:.2f}')} | 下轨 {_fmt(bb.get('lower'), '{:.2f}')}")
                
                # ADX趋势强度指标
                adx = ind.get('adx') or {}
                prompt_parts.append(f"ADX趋势强度: {_fmt(adx.get('adx'), '{:.1f}')} | +DI: {_fmt(adx.get('plus_di'), '{:.1f}')} | -DI: {_fmt(adx.get('minus_di'), '{:.1f}')}")
                
                # 成交量分析
                vol = ind.get('volume_analysis') or {}
                prompt_parts.append(f"成交量比率: {_fmt(vol.get('volume_ratio'), '{:.2f}')} | 量价趋势: {_fmt(vol.get('volume_trend'), '{:.2f}')}")
                
                # 支撑阻力位
                sr = ind.get('support_resistance') or {}
                resistance = sr.get('resistance', [])
                support = sr.get('support', [])
                if resistance:
                    res_str = ", ".join([f"{r:.2f}" for r in resistance[:2]])
                    prompt_parts.append(f"阻力位: {res_str}")
                if support:
                    sup_str = ", ".join([f"{s:.2f}" for s in support[:2]])
                    prompt_parts.append(f"支撑位: {sup_str}")
                
                # 4h 周期补充最近 K 线（供形态参考）
                if interval == "4h" and "df" in data and data["df"] is not None and len(data["df"]) >= 6:
                    df = data["df"].tail(6)
                    klines = df[["open", "high", "low", "close"]].round(2).to_dict("records")
                    prompt_parts.append(f"最近6根K线(4h): {klines}")
            
            prompt_parts.append("")
        
        # 添加交易规则
        prompt_parts.append("# 交易规则")
        prompt_parts.append(f"交易币种: {', '.join(config['trading']['symbols'])}")
        prompt_parts.append(f"默认杠杆: {config['trading']['default_leverage']}x | 最大杠杆: {config['trading']['max_leverage']}x")
        prompt_parts.append(f"仓位大小: {config['trading']['min_position_percent']}%-{config['trading']['max_position_percent']}%")
        prompt_parts.append(f"默认止盈: {config['risk']['take_profit_default_percent']}% | 默认止损: {config['risk']['stop_loss_default_percent']}%")
        prompt_parts.append(f"每日最大亏损: {config['risk']['max_daily_loss_percent']}% | 最大连续亏损: {config['risk']['max_consecutive_losses']}次")
        prompt_parts.append("")
        
        # 添加历史表现反馈（若有）
        if performance_feedback:
            prompt_parts.append("# 历史交易表现反馈")
            prompt_parts.append(performance_feedback)
            prompt_parts.append("")
        
        prompt_parts.append("# 技术指标使用指南")
        prompt_parts.append("- ADX > 25 表示趋势强劲，< 20 表示震荡市")
        prompt_parts.append("- 成交量比率 > 1.5 表示放量，< 0.5 表示缩量")
        prompt_parts.append("- 量价趋势 > 1 表示上涨放量，< 1 表示下跌放量")
        prompt_parts.append("- 支撑阻力位可用于设置止盈止损目标")
        prompt_parts.append("- 开仓前请确认：趋势强度(ADX) + 方向(+DI/-DI) + 成交量确认")
        prompt_parts.append("")
        
        # 添加决策要求
        prompt_parts.append("# 决策要求")
        prompt_parts.append("请综合技术指标、资金费率、市场情绪与新闻，为每个币种生成交易决策，包括：")
        prompt_parts.append("1. 交易动作: BUY_OPEN(开多), SELL_OPEN(开空), CLOSE(平仓), HOLD(持有)")
        prompt_parts.append("2. 决策理由: 详细说明决策依据")
        prompt_parts.append("3. 置信度: 0-1之间的数值，表示决策的置信程度")
        prompt_parts.append("4. 杠杆: 建议使用的杠杆倍数")
        prompt_parts.append("5. 仓位比例: 建议使用的资金比例")
        prompt_parts.append("6. 止盈止损: 建议的止盈止损百分比")
        prompt_parts.append("")
        prompt_parts.append("【重要】必须只输出一个JSON对象，不要有任何前缀或后缀。为每个交易对生成决策，key为交易对符号如BTCUSDT。")
        prompt_parts.append("请以JSON格式输出结果，示例格式如下：")
        prompt_parts.append("{")
        prompt_parts.append("  \"BTCUSDT\": {")
        prompt_parts.append("    \"action\": \"BUY_OPEN\",")
        prompt_parts.append("    \"reason\": \"4h周期上升趋势，RSI44未超买，MACD转正，短期看涨\",")
        prompt_parts.append("    \"confidence\": 0.75,")
        prompt_parts.append("    \"leverage\": 5,")
        prompt_parts.append("    \"position_percent\": 20,")
        prompt_parts.append("    \"take_profit_percent\": 5.0,")
        prompt_parts.append("    \"stop_loss_percent\": -2.0")
        prompt_parts.append("  },")
        prompt_parts.append("  \"ETHUSDT\": {")
        prompt_parts.append("    \"action\": \"HOLD\",")
        prompt_parts.append("    \"reason\": \"震荡整理，等待方向突破\",")
        prompt_parts.append("    \"confidence\": 0.6,")
        prompt_parts.append("    \"leverage\": 3,")
        prompt_parts.append("    \"position_percent\": 0,")
        prompt_parts.append("    \"take_profit_percent\": 0,")
        prompt_parts.append("    \"stop_loss_percent\": 0")
        prompt_parts.append("  }")
        prompt_parts.append("}")
        
        return "\n".join(prompt_parts)
    
    def build_single_symbol_prompt(self, symbol, market_analysis, account_summary, position_summary, config, sentiment_summary=None):
        """构建单个币种的提示词"""
        market_analyses = {symbol: market_analysis}
        return self.build_prompt(market_analyses, account_summary, position_summary, config, sentiment_summary)