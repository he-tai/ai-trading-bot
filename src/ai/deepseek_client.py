import requests
import json
import time

class DeepSeekClient:
    def __init__(self, api_key, base_url="https://api.deepseek.com/v1/chat/completions", timeout=300):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.timeout = timeout  # deepseek-reasoner 推理较慢，默认 300 秒
    
    def generate_response(self, messages, model="deepseek-reasoner", temperature=0.7, max_tokens=4096, retries=2):
        """生成AI响应。deepseek-reasoner 推理较慢，超时或网络错误时自动重试"""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            payload["response_format"] = {"type": "json_object"}
        except Exception:
            pass
        for attempt in range(retries + 1):
            try:
                response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=self.timeout)
                result = response.json()
                if not response.ok and "response_format" in payload:
                    err = result.get("error", {})
                    if "response_format" in str(err.get("message", "")).lower() or err.get("code") == "invalid_request_error":
                        del payload["response_format"]
                        response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=self.timeout)
                        result = response.json()
                response.raise_for_status()
                return result
            except requests.exceptions.Timeout:
                print(f"DeepSeek API请求超时 (尝试 {attempt + 1}/{retries + 1})，{self.timeout}秒")
                if attempt < retries:
                    time.sleep(5)
                    continue
                return None
            except requests.exceptions.RequestException as e:
                print(f"DeepSeek API网络请求失败 (尝试 {attempt + 1}/{retries + 1}): {e}")
                if attempt < retries:
                    time.sleep(5)
                    continue
                return None
            except json.JSONDecodeError:
                print("DeepSeek API返回的响应不是有效的JSON格式")
                return None
            except Exception as e:
                print(f"DeepSeek API调用失败: {e}")
                return None
        return None
    
    def get_trading_decision(self, prompt):
        """获取交易决策"""
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的加密货币交易分析师，擅长基于多维度数据分析进行交易决策。请根据提供的市场数据，生成交易决策。\n\n重要：必须输出纯JSON格式，不要包含任何解释文字。每个reason字段保持简短（一句话），不要换行，不要使用未转义的双引号。直接输出JSON对象，例如：{\"BTCUSDT\":{\"action\":\"BUY_OPEN\",\"reason\":\"...\",\"confidence\":0.75,\"leverage\":5,\"position_percent\":20,\"take_profit_percent\":5,\"stop_loss_percent\":-2}}"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        result = self.generate_response(messages)
        if result and "choices" in result:
            msg = result["choices"][0].get("message", {})
            # deepseek-reasoner: content=最终答案, reasoning_content=推理过程
            content = (msg.get("content") or "").strip()
            if not content:
                content = (msg.get("reasoning_content") or "").strip()
            return content if content else None
        return None
    
    def analyze_market(self, market_data):
        """分析市场数据"""
        # 构建分析提示词
        prompt = f"请分析以下市场数据，并提供详细的市场分析和交易建议：\n{json.dumps(market_data, indent=2)}"
        
        # 获取AI分析结果
        analysis = self.get_trading_decision(prompt)
        return analysis