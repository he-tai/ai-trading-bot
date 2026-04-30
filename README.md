# Hermes-AI - 智能量化交易机器人

一个基于 DeepSeek AI 的智能加密货币期货量化交易框架，支持币安 Binance U本位永续合约自动交易。

本项目旨在打造一个高性能、可扩展的 AI 量化交易系统，通过多维度数据分析和深度学习模型，实现稳定的投资收益。

## ✨ 特性

### 🤖 AI 驱动

- **DeepSeek Reasoning Model**: 使用 deepseek-reasoner 模型进行深度推理分析
- **多维度决策**: AI 综合分析技术指标、市场情绪、资金费率等多个维度
- **思维链推理**: 展示完整的 AI 推理过程，决策更加透明可信

### 📊 多周期技术分析

- **多时间框架**: 支持 5m、15m、1h、4h、1d 等多个周期
- **丰富技术指标**: RSI、MACD、EMA、SMA、ATR、布林带、KDJ、MFI
- **K线模式识别**: 分析最近 18 根 K 线走势

### 📰 新闻与情绪分析

- **恐惧贪婪指数**: 免费获取 Alternative.me 市场情绪（0-100）
- **RSS 免费新闻源**: 默认抓取 CoinDesk / Cointelegraph / Decrypt（无需 API Key）

### 🛡️ 风险管理

- **仓位控制**: 最小/最大仓位限制（默认 10%-30%）
- **每日最大亏损限制**: 默认 10%
- **连续亏损保护**: 最大连续亏损次数限制
- **杠杆管理**: 可配置 1-100 倍杠杆
- **止盈止损**: 自动设置止盈止损订单

### 💹 双向交易

- **做多 (LONG)**: 看涨时开多仓
- **做空 (SHORT)**: 看跌时开空仓
- **灵活持仓**: 支持同时持有多个方向的仓位
- **自动平仓**: AI 决策 + 止盈止损自动平仓

### 🔄 多币种支持

- **一键分析**: 单次 API 调用分析多个币种
- **独立决策**: 每个币种独立分析和决策
- **智能优化**: 综合考虑账户状态和历史决策

### 📋 决策日志与监控

- **详细决策日志**: 每轮上下文、AI 决策、执行结果写入 `logs/decisions.log`
- **Web 控制面板**: 查看运行日志/决策日志、持仓、支持手动关单

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Binance 期货账户（U本位合约）
- DeepSeek API Key

### 安装步骤

1. **准备项目**

   ```bash
   # 进入项目根目录
   cd ai-trading-bot
   ```

2. **安装依赖**

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip3 install -r requirements.txt
   ```

3. **配置环境变量**

   ```bash
   cp config/env.example .env
   # 编辑 .env 文件，填入你的 API 凭证
   ```

   `.env` 文件内容：

   ```
   # Binance API 配置
   BINANCE_API_KEY=your_binance_api_key_here
   BINANCE_SECRET=your_binance_secret_here

   # DeepSeek API 配置
   DEEPSEEK_API_KEY=your_deepseek_api_key_here

   # 生产环境必填（控制面板 API 鉴权；未设置将拒绝启动 dashboard）
   DASHBOARD_API_KEY=your_long_random_secret

   # 生产环境必填（CORS 白名单；未设置将拒绝启动 dashboard）
   DASHBOARD_ALLOWED_ORIGINS=https://your-domain.com

   # 可选：RSS 新闻源（未设置则使用内置默认源）
   NEWS_RSS_SOURCES=https://www.coindesk.com/arc/outboundfeeds/rss/,https://cointelegraph.com/rss,https://decrypt.co/feed
   ```

4. **配置交易参数**
   编辑 `config/trading_config.json`:

   ```json
   {
     "trading": {
       "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
       "default_leverage": 3,
       "max_leverage": 100,
       "min_position_percent": 10,
       "max_position_percent": 30,
       "reserve_percent": 20
     },
     "risk": {
       "max_daily_loss_percent": 10,
       "max_consecutive_losses": 5,
       "stop_loss_default_percent": 2,
       "take_profit_default_percent": 5
     },
     "ai": {
       "model": "deepseek-reasoner",
       "temperature": 0.7,
       "max_tokens": 2000,
       "timeout_seconds": 300
     },
     "schedule": {
       "interval_seconds": 180,
       "retry_times": 3,
       "retry_delay_seconds": 5
     }
   }
   ```

   **中文注释版本**：
   我们提供了带有详细中文注释的配置文件示例 `config/trading_config.json.example`，方便中文用户理解各个参数的含义。您可以参考此示例文件来修改您的配置。

5. **运行程序**

   ```bash
   # 前台运行
   python src/main.py

   # 后台运行（日志自动写入 logs/bot.log，需先创建目录）
   mkdir -p logs
   nohup python src/main.py > /dev/null 2>&1 &

   # 查看日志
   tail -f logs/bot.log
   tail -n 100 logs/bot.log

   # 进程管理
   ps aux | grep main.py
   pkill -f "main.py"
   ```

6. **Web 控制面板**（可选）

   可单独启动控制面板查看日志、持仓，并支持手动关单：

   ```bash
   # 前台运行
   python run_dashboard.py --port 5000

   # 后台运行
   nohup python run_dashboard.py --port 5000 &
   ```

   访问 <http://localhost:5000> 即可使用。控制面板会：
   - 切换查看运行日志（bot.log）或决策日志（decisions.log）
   - 显示当前持仓列表（每 30 秒自动刷新）
   - 支持对任意持仓点击「关单」进行手动平仓
   - 页面右上角需填写 `DASHBOARD_API_KEY`（否则 API 返回 401）

### Docker 部署

1. 在项目根目录准备 `.env`（可参考 `config/env.example`），至少包含 `BINANCE_API_KEY`、`BINANCE_SECRET`、`DEEPSEEK_API_KEY`，并且 **必须设置** `DASHBOARD_API_KEY` 与 `DASHBOARD_ALLOWED_ORIGINS`（否则 dashboard 拒绝启动）。
2. 确保存在 `config/trading_config.json`；`docker-compose` 已将 `./config` 挂载为只读，修改宿主机配置即可生效。
3. 启动：

   ```bash
   mkdir -p logs
   docker compose build
   docker compose up -d
   ```

4. Dashboard 默认映射宿主机 `5000` 端口（可在 `.env` 中设置 `DASHBOARD_PUBLISH_PORT` 覆盖）。探活接口：`GET /api/health`（无需鉴权）。Compose 已内置 healthcheck、只读根文件系统、非 root 运行与基础资源限制。

5. **从本机同步到远程服务器**（需已配置 `ssh 用户@服务器` 免密登录）：`chmod +x scripts/deploy.sh && ./scripts/deploy.sh ubuntu@你的服务器IP`。首次请在服务器上创建目录并单独上传 `.env`（脚本不会同步本机 `.env`）。

### 后台启动

生产环境建议使用 `nohup` 将服务置于后台运行，关闭终端后进程仍会继续执行。

#### 交易机器人后台启动

```bash
# 1. 创建日志目录（首次运行需执行）
mkdir -p logs

# 2. 后台启动交易机器人
# 日志自动写入 logs/bot.log，stdout/stderr 重定向到 /dev/null 避免重复
nohup python src/main.py > /dev/null 2>&1 &

# 3. 查看运行状态
ps aux | grep main.py

# 4. 查看日志
tail -f logs/bot.log          # 实时跟踪
tail -n 100 logs/bot.log      # 最近 100 行

# 5. 停止进程
pkill -f "main.py"
```

#### Web 控制面板后台启动

```bash
# 1. 创建日志目录（若尚未创建）
mkdir -p logs

# 2. 后台启动控制面板（默认端口 5000）
# 重定向输出避免 nohup.out 及 "ignoring input and appending output" 提示
nohup python run_dashboard.py --port 5000 >> logs/dashboard.log 2>&1 &

# 3. 查看运行状态
ps aux | grep run_dashboard

# 4. 访问
# 浏览器打开 http://localhost:5000（或 http://localhost:5080 若使用备用端口）

# 5. 停止进程
pkill -f "run_dashboard.py"
```

**常见问题**：① 端口冲突（`Address already in use`）：先 `pkill -f "run_dashboard.py"` 或改用 `--port 5080`。② 后台启动后进程退出：项目使用 waitress 替代 Flask 开发服务器，请执行 `pip install waitress` 后重试。③ Cloudflare 返回 400：已添加 ProxyFix 支持反向代理；若仍报错，检查 Cloudflare SSL 模式（源站为 HTTP 时选「灵活」），或先用 `http://服务器IP:端口` 直连测试。④ API 返回 401：已配置 `DASHBOARD_API_KEY` 时，请求头需带 `X-API-Key` 或在页面输入框填入相同 Key。

#### 一键启动（可选）

若需同时后台运行交易机器人和控制面板：

```bash
mkdir -p logs
nohup python src/main.py > /dev/null 2>&1 &
nohup python run_dashboard.py --port 5000 >> logs/dashboard.log 2>&1 &
```

## 📁 项目结构

```
hermes-ai/
├── Dockerfile                   # 容器镜像
├── docker-compose.yml           # bot + dashboard 编排
├── .dockerignore
├── config/                      # 配置文件
│   ├── env.example              # 环境变量示例
│   ├── trading_config.json      # 交易配置
│   └── trading_config.json.example  # 带中文注释的配置示例
├── src/                         # 源代码
│   ├── main.py                  # 主程序入口
│   ├── ai/                      # AI 相关
│   │   ├── deepseek_client.py   # DeepSeek API 客户端
│   │   ├── prompt_builder.py    # 提示词构建器
│   │   └── decision_parser.py   # 决策解析器
│   ├── api/                     # 交易所 API
│   │   └── binance_client.py    # 币安客户端
│   ├── config/                  # 配置管理
│   │   ├── config_loader.py     # 配置加载器
│   │   └── env_manager.py       # 环境变量管理
│   ├── data/                    # 数据管理
│   │   ├── market_data.py       # 市场数据管理器
│   │   ├── position_data.py     # 持仓数据管理器
│   │   ├── account_data.py      # 账户数据管理器
│   │   └── news_data.py         # 新闻与情绪数据（恐惧贪婪、RSS）
│   ├── trading/                 # 交易执行
│   │   ├── trade_executor.py    # 交易执行器
│   │   ├── position_manager.py  # 仓位管理器
│   │   └── risk_manager.py      # 风险管理器
│   ├── utils/                   # 工具类
│   │   ├── indicators.py        # 技术指标计算
│   │   ├── logger.py            # 日志输出到文件
│   │   └── decision_logger.py   # 决策日志记录
│   └── web/                     # Web 控制面板
│       └── app.py               # 控制面板服务（日志、持仓、关单）
├── docs/                        # 文档
│   └── OPTIMIZATION_REPORT.md  # 优化建议报告
├── logs/                        # 运行日志目录（自动创建）
│   ├── bot.log                  # 主运行日志
│   ├── decisions.log            # 详细决策日志（每轮上下文、AI决策、执行结果）
│   └── dashboard.log            # 控制面板运行日志
├── run_dashboard.py             # 启动 Web 控制面板
├── requirements.txt             # Python 依赖
└── README.md                    # 项目说明
```

## 🏗️ 核心模块

### 1. AI 决策引擎 (src/ai/)

- **DeepSeek Client**: 调用 DeepSeek API 进行推理分析
- **Prompt Builder**: 构建多维度市场分析提示词
- **Decision Parser**: 解析 AI 返回的 JSON 格式决策

### 2. 交易所接口 (src/api/)

- **Binance Client**: 完整的币安期货 API 封装

### 3. 数据管理 (src/data/)

- **Market Data Manager**: 多周期 K 线获取和技术指标计算
- **Account Data Manager**: 账户信息管理
- **Position Data Manager**: 持仓信息管理
- **News Data Manager**: 恐惧贪婪指数、RSS 新闻（可选）

### 4. 风险管理 (src/trading/)

- **Risk Manager**: 仓位大小限制、每日最大亏损检查、连续亏损保护
- **Position Manager**: 仓位管理和多币种持仓追踪
- **Trade Executor**: 开仓/平仓执行、止盈止损设置

### 5. 技术指标与工具 (src/utils/)

- **Indicators**: RSI、MACD、EMA、SMA、ATR、布林带、KDJ、MFI
- **Logger**: 日志输出到文件
- **Decision Logger**: 决策详情写入日志

## 🤖 AI 决策示例

### 输入（市场数据）

```
=== BTC/USDT ===
价格: $95,000.00 | 24h: +1.23% | 15m: +0.50%
资金费率: 0.000100 (多头付费) | 持仓量: 1,000,000

【4h周期】
RSI: 44.5 | MACD: 0.0025
EMA20: 95,200 | EMA50: 94,500
最近18根K线（OHLC）: ...
```

### 输出（AI 决策）

```json
{
  "BTCUSDT": {
    "action": "BUY_OPEN",
    "reason": "4h周期上升趋势，RSI44未超买，MACD转正，短期看涨",
    "confidence": 0.75,
    "leverage": 5,
    "position_percent": 20,
    "take_profit_percent": 5.0,
    "stop_loss_percent": -2.0
  }
}
```

## ⚙️ 配置说明

### 交易配置 (trading_config.json)

- **trading**: 交易相关配置
  - `symbols`: 交易币种列表
  - `default_leverage`: 默认杠杆倍数
  - `max_leverage`: 最大杠杆倍数
  - `min_position_percent`: 最小仓位占比
  - `max_position_percent`: 最大仓位占比
  - `reserve_percent`: 预留资金占比

- **risk**: 风险控制配置
  - `max_daily_loss_percent`: 每日最大亏损百分比
  - `max_consecutive_losses`: 最大连续亏损次数
  - `stop_loss_default_percent`: 默认止损百分比
  - `take_profit_default_percent`: 默认止盈百分比

- **ai**: AI 相关配置
  - `model`: AI 模型名称
  - `temperature`: 模型温度参数
  - `max_tokens`: 最大 token 数
  - `timeout_seconds`: API 超时秒数（deepseek-reasoner 推理较慢，默认 300）

- **schedule**: 调度配置
  - `interval_seconds`: 交易周期（秒）
  - `retry_times`: 重试次数
  - `retry_delay_seconds`: 重试延迟（秒）

## 🛡️ 安全建议

### API 权限控制

- 仅授予必要的权限（期货交易）
- 不要授予提币权限
- 定期轮换 API 密钥

### 资金管理

- 使用小额资金进行测试
- 设置合理的最大亏损限制
- 定期检查账户状态

### 风险管理

- 不要过度杠杆（建议 3-10 倍）
- 监控市场异常波动
- 设置止损保护

## 📝 运行日志示例

```
============================================================
🚀 AI交易机器人启动中...
============================================================
✅ 配置加载完成
✅ 环境变量加载完成
✅ 币安API连接正常
✅ DeepSeek API连接正常
✅ 数据管理器初始化完成
✅ 交易执行器初始化完成
✅ AI组件初始化完成
============================================================
🎉 AI交易机器人启动成功！
============================================================

💰 账户信息:
   总权益: 10,000.00 USDT
   可用资金: 8,000.00 USDT
   未实现盈亏: +125.50 USDT
   保证金率: 150.25%

📊 持仓信息:
   ETHUSDT: LONG 0.1234 @ 3,200.00
     当前价格: 3,250.00
     未实现盈亏: +6.17 USDT
     杠杆: 5x

📈 市场分析中...
   分析完成: BTCUSDT
   分析完成: ETHUSDT

🤖 调用AI进行交易决策...
📝 解析AI决策...

🎯 AI多币种决策总结:
   BTCUSDT: BUY_OPEN - 4h周期上升趋势，RSI44未超买，MACD转正，短期看涨
     置信度: 0.75 | 杠杆: 5x | 仓位: 20%
   ETHUSDT: HOLD - 震荡整理，等待方向突破
     置信度: 0.60 | 杠杆: 3x | 仓位: 0%

⚡ 执行交易...
开多成功: BTCUSDT 0.021 @ 市价
设置止盈成功: BTCUSDT SELL 99750.00 0.021
设置止损成功: BTCUSDT SELL 93100.00 0.021

============================================================
⏰ 等待下一个交易周期...
============================================================
```

## 🎯 使用场景

- **趋势跟踪**: 基于多周期技术指标识别趋势
- **反转交易**: 捕捉超买超卖区域的反弹
- **套利交易**: 利用资金费率差异
- **网格交易**: 配合止盈止损进行区间交易
- **多币种组合**: 分散风险，提高收益稳定性

## 🔧 自定义开发

### 添加自定义指标

编辑 `src/utils/indicators.py`:

```python
def calculate_custom_indicator(data: pd.DataFrame) -> float:
    """你的自定义指标"""
    # ... 计算逻辑
    return indicator_value
```

### 添加新的交易策略

编辑 `src/main.py`，在 `TradingBot` 类中添加自定义逻辑。

## 📊 性能监控与日志

### 日志文件说明

| 文件 | 说明 |
|------|------|
| `logs/bot.log` | 主运行日志，控制台输出同步写入 |
| `logs/decisions.log` | 决策日志，每轮上下文、AI 决策、执行结果 |
| `logs/dashboard.log` | Web 控制面板运行日志 |

### 监控建议

- 查看 `logs/bot.log` 中的交易记录
- 复盘 `logs/decisions.log` 分析 AI 决策准确性
- 在 Web 控制面板切换「运行日志」/「决策日志」查看
- 监控账户盈亏变化，调整参数优化收益

### 完整使用流程

```
安装依赖 → 配置 .env → 配置 trading_config.json → 运行程序 → 启动控制面板（可选）
    ↓           ↓                    ↓                    ↓
  pip install  API Key 填入        交易币种、杠杆等         python src/main.py
                                                       python run_dashboard.py
```

### 扩展阅读

- 优化建议与问题排查：`docs/OPTIMIZATION_REPORT.md`

## ❓ 常见问题

| 问题 | 解决方案 |
|------|----------|
| 端口被占用 | `pkill -f "run_dashboard.py"` 或改用 `--port 5080` |
| 后台启动后进程退出 | 执行 `pip install waitress` 后重试 |
| DeepSeek API 超时 | 在 `trading_config.json` 的 `ai` 中增加 `timeout_seconds`（如 600） |
| 控制面板 400 错误 | 检查 Cloudflare SSL 模式（源站 HTTP 选「灵活」），或直连测试 |
| 无恐惧贪婪/新闻 | 恐惧贪婪自动获取；新闻默认走 RSS（可在 `.env` 自定义 `NEWS_RSS_SOURCES`） |
| 决策日志为空 | 确保至少运行完一个交易周期，AI 返回决策后才会写入 |

## ⚠️ 免责声明

本软件仅供学习和研究使用。加密货币交易存在高风险，可能导致资金损失。使用本软件进行实盘交易的风险由使用者自行承担。开发者不对任何交易损失负责。

## 📜 License

MIT License

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 电子邮件：<your@email.com>
- 项目地址：请根据实际仓库路径填写

---

## 💰 收款码

如果这个项目对你有帮助，欢迎请作者喝杯咖啡，支持持续迭代与维护。

![微信收款码](docs/alipay.jpg)
![支付宝收款码](docs/wechat.jpg)

---

## 📚 文档索引

| 章节 | 内容 |
|------|------|
| [快速开始](#-快速开始) | 安装、配置、运行 |
| [后台启动](#后台启动) | 生产环境部署 |
| [项目结构](#-项目结构) | 目录与模块说明 |
| [配置说明](#️-配置说明) | 参数详解 |
| [性能监控](#-性能监控与日志) | 日志与监控 |
| [常见问题](#-常见问题) | 排错速查 |
| [收款码](#-收款码) | 支持开发 |
| [优化报告](docs/OPTIMIZATION_REPORT.md) | 深度优化建议 |

---

⭐ 如果这个项目对你有帮助，欢迎使用和定制！

Made with ❤️ by Hermes-AI Team
