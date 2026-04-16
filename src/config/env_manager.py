import os
from dotenv import load_dotenv

class EnvManager:
    def __init__(self, env_file=".env"):
        self.env_file = env_file
        self.load_env()
    
    def load_env(self):
        """加载环境变量"""
        load_dotenv(self.env_file)
    
    def get_binance_api_key(self):
        """获取币安API密钥"""
        return os.getenv("BINANCE_API_KEY")
    
    def get_binance_secret(self):
        """获取币安API密钥"""
        return os.getenv("BINANCE_SECRET")
    
    def get_deepseek_api_key(self):
        """获取DeepSeek API密钥"""
        return os.getenv("DEEPSEEK_API_KEY")
    
    def validate(self):
        """验证环境变量是否完整"""
        required_vars = [
            "BINANCE_API_KEY",
            "BINANCE_SECRET",
            "DEEPSEEK_API_KEY"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        
        return True