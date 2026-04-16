import json
import re

class DecisionParser:
    """AI 交易决策解析器，支持多种格式和常见错误修复"""
    
    def __init__(self):
        pass
    
    def extract_json(self, text):
        """从文本中提取 JSON，支持多种格式"""
        if not text or not isinstance(text, str):
            return ""
        text = text.strip()
        # 移除 BOM 和 <think>...</think>
        text = text.replace('\ufeff', '')
        text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()
        
        # 1. 优先提取 ```json ... ``` 或 ``` ... ```
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_block:
            return code_block.group(1).strip()
        
        # 2. 查找最后一个完整的 {...}（AI 常在末尾输出 JSON）
        brace_count = 0
        start = -1
        for i, c in enumerate(text):
            if c == '{':
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0 and start >= 0:
                    candidate = text[start:i+1]
                    if self._looks_like_decision_json(candidate):
                        return candidate
        # 3. 回退到贪婪匹配
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        return text
    
    def _looks_like_decision_json(self, s):
        """粗略判断是否为决策 JSON（含 BTCUSDT 等交易对）"""
        return 'USDT' in s and ('action' in s or 'BUY' in s or 'HOLD' in s)
    
    def _fix_common_json_errors(self, json_str):
        """修复 LLM 常见的 JSON 错误"""
        # 1. 字符串内换行 -> 空格
        json_str = self._preprocess_json(json_str)
        # 2. 尾随逗号 ,} 或 ,]
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        # 3. 移除控制字符
        json_str = ''.join(c for c in json_str if ord(c) >= 32 or c in '\n\t')
        return json_str
    
    def _preprocess_json(self, json_str):
        """将字符串值内的换行/制表符替换为空格"""
        result = []
        i = 0
        in_string = False
        escape = False
        while i < len(json_str):
            c = json_str[i]
            if escape:
                result.append(c)
                escape = False
            elif c == '\\' and in_string:
                result.append(c)
                escape = True
            elif c == '"' and not in_string:
                in_string = True
                result.append(c)
            elif c == '"' and in_string:
                in_string = False
                result.append(c)
            elif in_string and c in '\n\r\t\x0c':
                result.append(' ')
            else:
                result.append(c)
            i += 1
        return ''.join(result)
    
    def _extract_decision_dict(self, obj):
        """从可能嵌套的结构中提取 {symbol: decision} 字典"""
        if not isinstance(obj, dict):
            return None
        # 直接是 {BTCUSDT: {...}, ETHUSDT: {...}}
        if any('USDT' in str(k).upper() for k in obj.keys()):
            return obj
        # 嵌套: {result: {...}}, {data: {...}}, {decision: {...}}
        for key in ('result', 'data', 'decision', 'trading', 'decisions'):
            if key in obj and isinstance(obj[key], dict):
                inner = obj[key]
                if any('USDT' in str(k).upper() for k in inner.keys()):
                    return inner
        return None
    
    def _normalize_symbol(self, key):
        """标准化交易对格式为 BTCUSDT"""
        if not isinstance(key, str):
            return str(key).upper()
        s = key.upper().replace('-', '').replace('_', '')
        if not s.endswith('USDT'):
            s = s + 'USDT' if len(s) <= 6 else s
        return s
    
    def parse_decision(self, decision_text):
        """解析交易决策"""
        if not decision_text:
            return None
        json_text = self.extract_json(decision_text)
        if not json_text:
            return None
        
        last_error = None
        for raw in [json_text, self._fix_common_json_errors(json_text)]:
            try:
                obj = json.loads(raw)
                decision = self._extract_decision_dict(obj)
                if decision:
                    return decision
                if isinstance(obj, dict) and obj:
                    return obj
            except json.JSONDecodeError as e:
                last_error = e
                continue
        if last_error:
            print(f"解析决策失败: {last_error}")
            print(f"  错误位置: 行{last_error.lineno} 列{last_error.colno}")
        return None
    
    def validate_decision(self, decision, symbols, config):
        """验证并规范化决策"""
        if not decision:
            return None
        validated = {}
        symbol_set = {s.upper().replace('-', '') for s in symbols}
        for key, val in decision.items():
            norm_key = self._normalize_symbol(key)
            if norm_key in symbol_set:
                matched = next((s for s in symbols if s.upper().replace('-', '') == norm_key), norm_key)
                if isinstance(val, dict):
                    validated[matched] = self.validate_symbol_decision(val, config)
                elif isinstance(val, str):
                    validated[matched] = self.validate_symbol_decision({"action": val}, config)
        return validated if validated else None
    
    def validate_symbol_decision(self, symbol_decision, config):
        """验证单个币种决策"""
        if not isinstance(symbol_decision, dict):
            symbol_decision = {"action": str(symbol_decision)}
        default_action = "HOLD"
        default_confidence = 0.5
        default_leverage = config['trading'].get('default_leverage', 3)
        default_max_leverage = config['trading'].get('max_leverage', 100)
        default_position_percent = 0
        default_take_profit = config['risk'].get('take_profit_default_percent', 5)
        default_stop_loss = -config['risk'].get('stop_loss_default_percent', 2)
        
        action = str(symbol_decision.get('action', default_action)).upper()
        valid_actions = ['BUY_OPEN', 'SELL_OPEN', 'CLOSE', 'HOLD']
        if action not in valid_actions:
            action = default_action
        
        confidence = symbol_decision.get('confidence', default_confidence)
        try:
            confidence = max(0, min(1, float(confidence)))
        except (TypeError, ValueError):
            confidence = default_confidence
        
        leverage = symbol_decision.get('leverage', default_leverage)
        try:
            leverage = max(1, min(default_max_leverage, int(float(leverage))))
        except (TypeError, ValueError):
            leverage = default_leverage
        
        position_percent = symbol_decision.get('position_percent', default_position_percent)
        try:
            min_pos = config['trading'].get('min_position_percent', 0)
            max_pos = config['trading'].get('max_position_percent', 30)
            position_percent = max(min_pos, min(max_pos, float(position_percent)))
        except (TypeError, ValueError):
            position_percent = default_position_percent
        
        if action in ['HOLD', 'CLOSE']:
            position_percent = 0
        
        take_profit = symbol_decision.get('take_profit_percent', default_take_profit)
        stop_loss = symbol_decision.get('stop_loss_percent', default_stop_loss)
        try:
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            take_profit = default_take_profit
        try:
            stop_loss = float(stop_loss)
        except (TypeError, ValueError):
            stop_loss = default_stop_loss

        # 保护性约束：开仓时强制有效止损，避免裸单
        if action in ['BUY_OPEN', 'SELL_OPEN']:
            if stop_loss > 0:
                stop_loss = -stop_loss
            stop_loss = min(-0.1, max(-20.0, stop_loss))
            take_profit = max(0.1, min(30.0, take_profit))
        else:
            take_profit = 0
            stop_loss = 0
        
        return {
            'action': action,
            'reason': str(symbol_decision.get('reason', ''))[:200],
            'confidence': confidence,
            'leverage': leverage,
            'position_percent': position_percent,
            'take_profit_percent': take_profit,
            'stop_loss_percent': stop_loss
        }
    
    def parse_and_validate(self, decision_text, symbols, config):
        """解析并验证"""
        decision = self.parse_decision(decision_text)
        return self.validate_decision(decision, symbols, config)
