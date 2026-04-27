import time
import json
import os
from config.config_loader import ConfigLoader
from utils.logger import setup_file_logging
from config.env_manager import EnvManager
from api.binance_client import BinanceClient
from data.market_data import MarketDataManager
from data.account_data import AccountDataManager
from data.position_data import PositionDataManager
from data.news_data import NewsDataManager
from ai.deepseek_client import DeepSeekClient
from ai.prompt_builder import PromptBuilder
from ai.decision_parser import DecisionParser
from trading.risk_manager import RiskManager
from trading.position_manager import PositionManager
from trading.trade_executor import TradeExecutor
from utils.decision_logger import DecisionLogger
from utils.trade_performance import TradePerformanceTracker

class TradingBot:
    def __init__(self):
        # 加载配置
        self.config_loader = ConfigLoader()
        self.config = {
            'trading': self.config_loader.get_trading_config(),
            'risk': self.config_loader.get_risk_config(),
            'ai': self.config_loader.get_ai_config(),
            'schedule': self.config_loader.get_schedule_config(),
            'news': self.config_loader.config.get('news', {}) or {},
        }
        
        # 加载环境变量
        self.env_manager = EnvManager()
        self.env_manager.validate()
        
        # 初始化API客户端
        self.binance_client = BinanceClient(
            api_key=self.env_manager.get_binance_api_key(),
            api_secret=self.env_manager.get_binance_secret()
        )
        
        ai_config = self.config.get('ai', {})
        self.deepseek_client = DeepSeekClient(
            api_key=self.env_manager.get_deepseek_api_key(),
            timeout=ai_config.get('timeout_seconds', 300)
        )
        
        # 初始化数据管理器
        self.market_data_manager = MarketDataManager(self.binance_client)
        self.account_data_manager = AccountDataManager(self.binance_client)
        self.position_data_manager = PositionDataManager(self.binance_client)
        self.news_data_manager = NewsDataManager()
        
        # 初始化AI组件
        self.prompt_builder = PromptBuilder()
        self.decision_parser = DecisionParser()
        
        # 初始化交易组件
        self.risk_manager = RiskManager(self.config)
        self.position_manager = PositionManager(self.binance_client)
        self.trade_executor = TradeExecutor(
            self.binance_client,
            self.position_manager,
            self.risk_manager
        )
        
        # 交易币种
        self.symbols = self.config['trading'].get('symbols', ['BTCUSDT', 'ETHUSDT'])
        
        # 交易周期
        self.interval_seconds = self.config['schedule'].get('interval_seconds', 180)
        risk_cfg = self.config.get('risk', {})
        trading_cfg = self.config.get('trading', {})
        self.min_confidence_to_open = risk_cfg.get('min_confidence_to_open', 0.68)
        self.min_atr_percent = risk_cfg.get('min_atr_percent', 0.35)
        self.max_atr_percent = risk_cfg.get('max_atr_percent', 4.0)
        self.symbol_cooldown_minutes = trading_cfg.get('cooldown_minutes_per_symbol', 30)
        self.prevent_same_direction_add = trading_cfg.get('prevent_same_direction_add', True)
        self.require_trend_alignment = risk_cfg.get('require_1h_4h_trend_alignment', True)
        self.news_policy = self.config.get('news', {}) or {}
        self.last_trade_ts = {}
        
        # 决策日志（写入 logs/decisions.log）
        self.decision_logger = DecisionLogger()
        
        # 交易表现跟踪
        self.performance_tracker = TradePerformanceTracker()

    def _extract_indicator(self, analysis, interval, key):
        data = analysis.get('market_data', {}).get(interval, {}).get('indicators', {})
        value = data.get(key)
        if isinstance(value, dict):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _is_trend_aligned(self, analysis, action):
        if action not in ('BUY_OPEN', 'SELL_OPEN') or not self.require_trend_alignment:
            return True
        e1_20 = self._extract_indicator(analysis, '1h', 'ema20')
        e1_50 = self._extract_indicator(analysis, '1h', 'ema50')
        e4_20 = self._extract_indicator(analysis, '4h', 'ema20')
        e4_50 = self._extract_indicator(analysis, '4h', 'ema50')
        if None in (e1_20, e1_50, e4_20, e4_50):
            return True
        if action == 'BUY_OPEN':
            return e1_20 > e1_50 and e4_20 > e4_50
        return e1_20 < e1_50 and e4_20 < e4_50

    def _is_volatility_valid(self, analysis):
        atr_1h = self._extract_indicator(analysis, '1h', 'atr')
        price = float(analysis.get('price', 0) or 0)
        if atr_1h is None or price <= 0:
            return True
        atr_percent = (atr_1h / price) * 100
        return self.min_atr_percent <= atr_percent <= self.max_atr_percent

    def _is_volume_confirmed(self, analysis, action):
        """成交量确认：开仓需要有足够的成交量支持"""
        if action not in ('BUY_OPEN', 'SELL_OPEN'):
            return True
        
        vol_data = analysis.get('market_data', {}).get('1h', {}).get('volume_analysis', {})
        volume_ratio = vol_data.get('volume_ratio')
        
        # 如果没有成交量数据，默认允许（避免误杀）
        if volume_ratio is None:
            return True
        
        # 成交量比率 < 0.3 表示极度缩量，可能是假突破
        if volume_ratio < 0.3:
            return False
        
        return True

    def _is_trend_strong_enough(self, analysis, action):
        """趋势强度过滤：ADX > 20 才认为是有效趋势"""
        if action not in ('BUY_OPEN', 'SELL_OPEN'):
            return True
        
        adx_data = analysis.get('market_data', {}).get('1h', {}).get('adx', {})
        adx_value = adx_data.get('adx')
        
        # 如果没有ADX数据，默认允许（兼容旧逻辑）
        if adx_value is None:
            return True
        
        # ADX < 20 表示震荡市，不开仓
        return adx_value >= 20

    def _find_current_position(self, symbol, positions):
        for p in positions:
            if p.get('symbol') == symbol:
                return p
        return None

    def _strategy_gate(self, symbol, symbol_decision, market_analysis, current_positions, sentiment_summary=None):
        action = symbol_decision.get('action', 'HOLD')
        if action not in ('BUY_OPEN', 'SELL_OPEN'):
            return True, ""

        na = (sentiment_summary or {}).get("news_analysis") or {}
        hints = na.get("strategy_hints") or {}
        if hints.get("risk_off") and self.news_policy.get("block_open_on_risk_off", True):
            return False, "新闻风险闸: 安全/黑客类标题密集，暂停新开仓"

        macro_min = int(self.news_policy.get("macro_caution_min_hits", 3))
        macro_extra = float(self.news_policy.get("macro_extra_confidence", 0.06))
        macro_hits = int(hints.get("macro_stress_hits", 0))
        tailwind_min = int(self.news_policy.get("symbol_tailwind_min_hits", 2))
        tailwind_delta = float(self.news_policy.get("symbol_tailwind_confidence_delta", -0.03))

        sym_hits = (hints.get("symbol_title_hits") or {}).get(symbol, 0)
        effective_min = self.min_confidence_to_open
        if macro_hits >= macro_min:
            effective_min += macro_extra
        if sym_hits >= tailwind_min:
            effective_min = max(0.5, effective_min + tailwind_delta)

        if symbol_decision.get('confidence', 0) < effective_min:
            return False, f"置信度低于有效阈值({effective_min:.2f}, 含新闻调整)"

        last_ts = self.last_trade_ts.get(symbol)
        if last_ts:
            cooldown = self.symbol_cooldown_minutes * 60
            if time.time() - last_ts < cooldown:
                return False, f"冷却期内({self.symbol_cooldown_minutes}分钟)"

        if not self._is_trend_aligned(market_analysis, action):
            return False, "1h/4h 趋势不一致"

        if not self._is_volatility_valid(market_analysis):
            return False, f"ATR波动率不在区间({self.min_atr_percent}%~{self.max_atr_percent}%)"
        
        if not self._is_volume_confirmed(market_analysis, action):
            return False, "成交量极度缩量，可能是假突破"
        
        if not self._is_trend_strong_enough(market_analysis, action):
            return False, "ADX趋势强度不足(<20)，震荡市不开仓"

        if self.prevent_same_direction_add:
            pos = self._find_current_position(symbol, current_positions)
            if pos:
                direction = pos.get('direction')
                if (action == 'BUY_OPEN' and direction == 'LONG') or (action == 'SELL_OPEN' and direction == 'SHORT'):
                    return False, "已有同向持仓，禁止重复开仓"
        return True, ""
    
    def run(self):
        """运行交易机器人"""
        print("=" * 60)
        print("🚀 AI交易机器人启动中...")
        print("=" * 60)
        
        # 初始化检查
        self.initialize()
        
        print("=" * 60)
        print("🎉 AI交易机器人启动成功！")
        print("=" * 60)
        
        # 主循环
        cycle = 1
        while True:
            try:
                print(f"\n{'=' * 60}")
                print(f"📅 交易周期 #{cycle} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 60}")
                
                # 1. 获取账户信息
                account_summary = self.account_data_manager.get_account_summary()
                print(f"💰 账户信息:")
                print(f"   总权益: {account_summary['total_balance']:.2f} USDT")
                print(f"   可用资金: {account_summary['available_balance']:.2f} USDT")
                print(f"   未实现盈亏: {account_summary['unrealized_pnl']:.2f} USDT")
                print(f"   保证金率: {account_summary['margin_level']:.2f}%")
                
                # 2. 获取持仓信息
                position_summary = self.position_manager.get_position_summary()
                print(f"\n📊 持仓信息:")
                if position_summary['positions']:
                    for position in position_summary['positions']:
                        print(f"   {position['symbol']}: {position['direction']} {position['size']:.4f} @ {position['entry_price']:.2f}")
                        print(f"     当前价格: {position['mark_price']:.2f}")
                        print(f"     未实现盈亏: {position['unrealized_pnl']:.2f} USDT")
                        print(f"     杠杆: {position['leverage']}x")
                else:
                    print("   当前无持仓")
                
                # 3. 获取市场数据
                print(f"\n📈 市场分析中...")
                market_analyses = {}
                for symbol in self.symbols:
                    analysis = self.market_data_manager.analyze_market(symbol)
                    if analysis:
                        market_analyses[symbol] = analysis
                        print(f"   分析完成: {symbol}")
                    else:
                        print(f"   跳过: {symbol} (分析失败)")
                
                if not market_analyses:
                    print("⚠️ 无有效市场数据，跳过本周期")
                    time.sleep(self.interval_seconds)
                    cycle += 1
                    continue
                
                # 3.5 获取情绪与新闻（可选，失败不影响主流程）
                sentiment_summary = None
                try:
                    sentiment_summary = self.news_data_manager.get_sentiment_summary(
                        news_policy=self.news_policy,
                        trading_symbols=self.symbols,
                    )
                    if sentiment_summary:
                        fng = sentiment_summary.get("fear_greed")
                        if fng:
                            print(f"   恐惧贪婪指数: {fng['value']} ({fng['classification']})")
                        na = sentiment_summary.get("news_analysis")
                        if na and na.get("strategy_hints"):
                            h = na["strategy_hints"]
                            print(
                                f"   新闻策略信号: risk_off={h.get('risk_off')} "
                                f"macro={h.get('macro_stress_hits')} hack={h.get('hack_hits')}"
                            )
                except Exception as e:
                    print(f"   情绪数据获取跳过: {e}")
                
                # 决策日志：周期上下文（账户、持仓、情绪、市场摘要）
                self.decision_logger.log_cycle_start(cycle, account_summary, position_summary, sentiment_summary)
                self.decision_logger.log_market_summary(market_analyses)
                
                # 3.6 获取历史表现反馈（每 5 个周期更新一次）
                performance_feedback = None
                if cycle % 5 == 0:
                    performance_feedback = self.performance_tracker.get_feedback_for_ai(days=30)
                
                # 4. 构建AI提示词
                prompt = self.prompt_builder.build_prompt(
                    market_analyses,
                    account_summary,
                    position_summary,
                    self.config,
                    sentiment_summary,
                    performance_feedback
                )
                
                # 5. 获取AI决策
                print(f"\n🤖 调用AI进行交易决策...")
                decision_text = self.deepseek_client.get_trading_decision(prompt)
                
                if decision_text:
                    # 6. 解析决策
                    print(f"📝 解析AI决策...")
                    decision = self.decision_parser.parse_and_validate(
                        decision_text,
                        self.symbols,
                        self.config
                    )
                    if not decision:
                        print("⚠️ AI 决策解析失败或返回空，请检查 AI 是否返回了有效的 JSON 格式")
                        if decision_text:
                            preview = decision_text[:500] + "..." if len(decision_text) > 500 else decision_text
                            print(f"   AI 返回预览: {preview}")
                        self.decision_logger.log_decision_parse_fail(decision_text or "", "解析失败或返回空")
                    elif not any(d.get('action') in ('BUY_OPEN', 'SELL_OPEN', 'CLOSE') for d in decision.values()):
                        print("⚠️ AI 全部返回 HOLD，本周期无交易执行")
                    if decision:
                        print(f"\n🎯 AI多币种决策总结:")
                        for symbol, symbol_decision in decision.items():
                            print(f"   {symbol}: {symbol_decision['action']} - {symbol_decision['reason']}")
                            print(f"     置信度: {symbol_decision['confidence']:.2f} | 杠杆: {symbol_decision['leverage']}x | 仓位: {symbol_decision['position_percent']}%")
                        self.decision_logger.log_ai_decision(decision, decision_text[:500] if decision_text else None)
                        
                        # 7. 执行交易
                        print(f"\n⚡ 执行交易...")
                        has_trade = False
                        for symbol, symbol_decision in decision.items():
                            action = symbol_decision.get('action', 'HOLD')
                            if action == 'HOLD':
                                print(f"   {symbol}: HOLD，跳过")
                                continue
                            if action == 'CLOSE' and not any(p['symbol'] == symbol for p in position_summary['positions']):
                                print(f"   {symbol}: CLOSE 但无持仓，跳过")
                                self.decision_logger.log_execution(symbol, action, True, order_success=False, order_error="无持仓")
                                continue
                            gate_ok, gate_reason = self._strategy_gate(
                                symbol,
                                symbol_decision,
                                market_analyses.get(symbol, {}),
                                position_summary['positions'],
                                sentiment_summary,
                            )
                            if not gate_ok:
                                print(f"   ⛔ {symbol} 策略过滤跳过: {gate_reason}")
                                self.decision_logger.log_execution(symbol, action, False, risk_failed=[gate_reason])
                                continue
                            # 检查风险
                            # 为风险检查添加 symbol 信息（用于相关性检查）
                            symbol_decision_with_symbol = {**symbol_decision, 'symbol': symbol}
                            risk_check = self.risk_manager.check_risk(
                                symbol_decision_with_symbol,
                                account_summary['total_balance'],
                                position_summary['positions'],
                                account_summary['margin_level']
                            )
                            
                            if risk_check['approved']:
                                order = self.trade_executor.execute_trade(
                                    symbol,
                                    symbol_decision,
                                    account_summary['total_balance']
                                )
                                if order:
                                    print(f"   ✅ {symbol} 下单成功")
                                    has_trade = True
                                    self.last_trade_ts[symbol] = time.time()
                                    self.decision_logger.log_execution(symbol, action, True, order_success=True)
                                else:
                                    print(f"   ❌ {symbol} 下单失败（仓位为0或API异常）")
                                    self.decision_logger.log_execution(symbol, action, True, order_success=False, order_error="仓位为0或API异常")
                            else:
                                failed = [k for k, v in risk_check['checks'].items() if not v]
                                print(f"   ❌ {symbol} 风险检查未通过: {failed}")
                                self.decision_logger.log_execution(symbol, action, False, risk_failed=failed)
                        self.decision_logger.log_cycle_end(cycle, has_trade)
                    else:
                        self.decision_logger.log_cycle_end(cycle, False)
                else:
                    self.decision_logger.log_decision_parse_fail("", "AI 未返回有效内容")
                    self.decision_logger.log_cycle_end(cycle, False)
                
                # 8. 等待下一个周期
                print(f"\n{'=' * 60}")
                print(f"⏰ 等待下一个交易周期...")
                print(f"{'=' * 60}")
                time.sleep(self.interval_seconds)
                
                cycle += 1
                
            except KeyboardInterrupt:
                print(f"\n{'=' * 60}")
                print("🛑 交易机器人停止")
                print(f"{'=' * 60}")
                break
            except Exception as e:
                print(f"\n❌ 交易周期执行失败: {e}")
                print(f"⏰ 等待下一个交易周期...")
                time.sleep(self.interval_seconds)
                cycle += 1
    
    def initialize(self):
        """初始化检查"""
        print("✅ 配置加载完成")
        print("✅ 环境变量加载完成")
        
        # 测试API连接
        try:
            ticker = self.binance_client.get_ticker("BTCUSDT")
            print("✅ 币安API连接正常")
            # 检查持仓模式，双向持仓时提示
            if self.binance_client.get_position_mode():
                print("⚠️ 当前为双向持仓模式，已支持。若需单向持仓，请在币安APP中切换")
            
            # 测试DeepSeek API
            test_prompt = "测试连接"
            test_response = self.deepseek_client.get_trading_decision(test_prompt)
            print("✅ DeepSeek API连接正常")
            
        except Exception as e:
            print(f"❌ API连接失败: {e}")
            raise
        
        print("✅ 数据管理器初始化完成")
        print("✅ 交易执行器初始化完成")
        print("✅ AI组件初始化完成")

if __name__ == "__main__":
    # 日志输出到文件（默认项目根目录下 logs/bot.log）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.environ.get("BOT_LOG_PATH", os.path.join(project_root, "logs", "bot.log"))
    setup_file_logging(log_path)
    print(f"📁 日志已写入: {os.path.abspath(log_path)}")
    
    bot = TradingBot()
    bot.run()