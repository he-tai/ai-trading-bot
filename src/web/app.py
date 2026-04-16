"""Web 控制面板：查看日志、持仓，支持手动关单"""
import os
import sys
from dotenv import load_dotenv

# 项目根目录和 src 目录
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_src_root = os.path.join(_project_root, "src")
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

# 切换工作目录到项目根目录，以便正确加载 .env
os.chdir(_project_root)
load_dotenv(os.path.join(_project_root, ".env"))

from flask import Flask, jsonify, request, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix
from config.env_manager import EnvManager
from api.binance_client import BinanceClient
from trading.position_manager import PositionManager

app = Flask(__name__)
# 支持 Cloudflare、Nginx 等反向代理的 X-Forwarded-* 头
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

_dashboard_api_key = os.environ.get("DASHBOARD_API_KEY", "").strip()
_allowed_origins = [
    o.strip()
    for o in os.environ.get("DASHBOARD_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]


def _is_authorized():
    """校验 API Key：Header X-API-Key 或 Authorization: Bearer <key>"""
    if not _dashboard_api_key:
        return True
    header_key = request.headers.get("X-API-Key", "").strip()
    if header_key and header_key == _dashboard_api_key:
        return True
    auth = request.headers.get("Authorization", "").strip()
    if auth.startswith("Bearer ") and auth[7:].strip() == _dashboard_api_key:
        return True
    return False


@app.before_request
def _dashboard_auth_and_options():
    if request.method == "OPTIONS":
        return "", 204
    path = request.path or ""
    if path.startswith("/api/") and path != "/api/health":
        if _dashboard_api_key and not _is_authorized():
            return jsonify({"error": "unauthorized"}), 401


@app.after_request
def add_cors_headers(response):
    """CORS：配置了 DASHBOARD_ALLOWED_ORIGINS 则白名单，否则 *"""
    origin = request.headers.get("Origin", "")
    if _allowed_origins:
        if origin in _allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
    return response

# 全局实例（懒加载）
_binance_client = None
_position_manager = None
_config = None


def get_binance_client():
    global _binance_client
    if _binance_client is None:
        env = EnvManager()
        _binance_client = BinanceClient(
            api_key=env.get_binance_api_key(),
            api_secret=env.get_binance_secret()
        )
    return _binance_client


def get_position_manager():
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager(get_binance_client())
    return _position_manager


def _slug_log_id(filename_stem: str) -> str:
    """将文件名 stem 转为 URL/查询参数安全的 id（小写、点变下划线）"""
    s = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in filename_stem.lower())
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_") or "log"


def get_log_catalog():
    """
    可展示的日志流列表：固定顺序的核心日志 + logs 目录下其余 *.log。
    每项: {id, label, path, exists}
    """
    logs_dir = os.path.join(_project_root, "logs")
    bot_path = os.environ.get("BOT_LOG_PATH", os.path.join(logs_dir, "bot.log"))
    decisions_path = os.path.join(logs_dir, "decisions.log")
    stdout_path = os.path.join(logs_dir, "bot.stdout.log")

    entries = []
    seen_paths = set()

    def add(eid, label, path):
        ap = os.path.abspath(path)
        if ap in seen_paths:
            return
        seen_paths.add(ap)
        entries.append({
            "id": eid,
            "label": label,
            "path": path,
            "exists": os.path.isfile(path),
        })

    add("bot", "运行日志 (bot)", bot_path)
    add("decisions", "决策日志 (decisions)", decisions_path)
    add("stdout", "进程标准输出 (stdout)", stdout_path)

    if os.path.isdir(logs_dir):
        for name in sorted(os.listdir(logs_dir)):
            if not name.endswith(".log"):
                continue
            path = os.path.join(logs_dir, name)
            ap = os.path.abspath(path)
            if ap in seen_paths:
                continue
            stem = os.path.splitext(name)[0]
            eid = _slug_log_id(stem)
            # 避免与固定 id 冲突
            used_ids = {e["id"] for e in entries}
            base_id = eid
            n = 0
            while eid in used_ids:
                n += 1
                eid = f"{base_id}_{n}"
            add(eid, f"文件: {name}", path)

    return entries


def _path_for_log_type(log_type: str):
    """根据 catalog id 解析路径；未知 id 回退 bot。"""
    for item in get_log_catalog():
        if item["id"] == log_type:
            return item["path"]
    for item in get_log_catalog():
        if item["id"] == "bot":
            return item["path"]
    return os.path.join(_project_root, "logs", "bot.log")


def get_log_path(log_type="bot"):
    """兼容旧调用：获取单一路径"""
    return _path_for_log_type(log_type)


def read_log_tail(lines=500, log_type="bot"):
    """读取日志文件最后 N 行"""
    log_path = _path_for_log_type(log_type)
    if not os.path.exists(log_path):
        return f"[日志文件不存在: {log_path}]\n请先运行交易机器人 (python src/main.py) 以生成日志。"
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:]) if all_lines else "(空)"
    except Exception as e:
        return f"读取日志失败: {e}"


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 交易机器人 - 控制面板</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 20px;
        }
        h1 {
            font-size: 1.5rem;
            margin-bottom: 20px;
            color: #58a6ff;
        }
        .section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 1rem;
            color: #8b949e;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #30363d;
        }
        .positions-table {
            width: 100%;
            border-collapse: collapse;
        }
        .positions-table th, .positions-table td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #21262d;
        }
        .positions-table th {
            color: #8b949e;
            font-weight: 500;
        }
        .positions-table tr:hover {
            background: #21262d;
        }
        .pnl-positive { color: #3fb950; }
        .pnl-negative { color: #f85149; }
        .btn {
            padding: 6px 14px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-family: inherit;
        }
        .btn-close {
            background: #da3633;
            color: white;
        }
        .btn-close:hover {
            background: #b62324;
        }
        .btn-refresh {
            background: #238636;
            color: white;
            margin-bottom: 10px;
        }
        .btn-refresh:hover {
            background: #2ea043;
        }
        .log-container {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px;
            max-height: 56vh;
            overflow-y: auto;
            font-size: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .empty-state {
            color: #8b949e;
            padding: 20px;
            text-align: center;
        }
        .status-ok { color: #3fb950; }
        .status-err { color: #f85149; }
        .tabs {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 0;
        }
        .tab {
            padding: 8px 12px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            cursor: pointer;
            color: #8b949e;
            font-size: 12px;
            max-width: 100%;
        }
        .tab .tab-badge {
            display: inline-block;
            margin-left: 6px;
            padding: 1px 5px;
            border-radius: 4px;
            font-size: 10px;
            background: #30363d;
            color: #8b949e;
        }
        .tab.active .tab-badge { background: rgba(255,255,255,0.15); color: #c9d1d9; }
        .tab.missing { opacity: 0.75; }
        .tab.active {
            background: #238636;
            color: white;
            border-color: #238636;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        /* 日志类型切换：与早期「运行日志 / 决策日志」按钮一致 */
        .log-type-btn {
            background: #30363d;
            color: #8b949e;
            margin-bottom: 0;
        }
        .log-type-btn.active {
            background: #238636;
            color: #fff;
        }
        .log-type-btn.missing:not(.active) {
            opacity: 0.72;
        }
        .log-toolbar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }
        .log-toolbar-label {
            color: #8b949e;
            font-size: 12px;
            margin-right: 2px;
        }
        .log-toolbar-sep {
            color: #484f58;
            user-select: none;
            display: none;
        }
        .log-toolbar-sep.visible { display: inline; }
        .auto-refresh-bar {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            padding: 10px 14px;
            background: #21262d;
            border-radius: 6px;
            border: 1px solid #30363d;
        }
        .auto-refresh-bar label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            color: #8b949e;
            font-size: 13px;
        }
        .auto-refresh-bar input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }
        .auto-refresh-bar .freq-wrap {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .auto-refresh-bar input[type="number"] {
            width: 70px;
            padding: 6px 8px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            font-size: 13px;
        }
        .auto-refresh-bar input[type="number"]:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .api-key-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: auto;
        }
        .api-key-wrap input {
            width: 220px;
            padding: 6px 8px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #c9d1d9;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <h1>🤖 AI 交易机器人 - 控制面板</h1>

    <div class="auto-refresh-bar">
        <label>
            <input type="checkbox" id="auto-refresh-switch" checked>
            自动刷新
        </label>
        <span class="freq-wrap">
            <label for="auto-refresh-freq">间隔(秒)</label>
            <input type="number" id="auto-refresh-freq" value="10" min="5" max="300" step="1">
        </span>
        <span class="api-key-wrap">
            <label for="api-key-input">API Key</label>
            <input type="password" id="api-key-input" placeholder="与 DASHBOARD_API_KEY 一致">
        </span>
    </div>

    <div class="section">
        <h2>📊 当前持仓</h2>
        <button class="btn btn-refresh" id="btn-refresh-positions">刷新持仓</button>
        <div id="positions-container">
            <div class="empty-state">加载中...</div>
        </div>
    </div>

    <div class="section" style="height: 64vh">
        <h2>📁 运行日志</h2>
        <div class="log-toolbar">
            <span class="log-toolbar-label">切换</span>
            <button type="button" class="btn log-type-btn active" id="btn-log-bot" data-log-id="bot">运行日志</button>
            <button type="button" class="btn log-type-btn" id="btn-log-decisions" data-log-id="decisions">决策日志</button>
            <span class="log-toolbar-sep" id="log-extra-sep">|</span>
            <div id="log-type-extra-btns" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;"></div>
            <button class="btn btn-refresh" id="btn-refresh-logs" style="margin-left:auto;">刷新当前</button>
        </div>
        <p id="log-path-hint" style="font-size:11px;color:#6e7681;margin-bottom:8px;word-break:break-all;"></p>
        <div class="log-container" id="log-container">加载中...</div>
    </div>

    <div class="section" style="padding: 8px;">
        <button class="btn" style="background:#30363d;color:#8b949e;font-size:12px;" id="btn-check-status">🔧 诊断</button>
        <pre id="status-output" style="display:none;margin-top:8px;font-size:11px;color:#8b949e;"></pre>
    </div>

    <script>
        var p = window.location.pathname;
        var API_BASE = (p === '/' || p === '' || p === '/index.html') ? '' : p.replace(/\/$/, '');
        function apiFetch(path, opts, retries) {
            retries = retries || 0;
            opts = opts || {};
            opts.cache = 'no-store';
            opts.headers = opts.headers || {};
            var apiKey = localStorage.getItem('dashboard_api_key') || '';
            if (apiKey) opts.headers['X-API-Key'] = apiKey;
            opts.headers['Cache-Control'] = 'no-cache';
            opts.headers['Pragma'] = 'no-cache';
            var url = API_BASE + path + (path.indexOf('?') >= 0 ? '&' : '?') + '_=' + Date.now();
            var t = null;
            try {
                var controller = new AbortController();
                opts.signal = opts.signal || controller.signal;
                t = setTimeout(function() { controller.abort(); }, 15000);
            } catch (_) {}
            return fetch(url, opts).then(function(r) {
                if (t) clearTimeout(t);
                if (!r.ok) {
                    if ((r.status === 400 || r.status === 502 || r.status === 503) && retries < 1) {
                        return new Promise(function(res) { setTimeout(res, 1500); }).then(function() {
                            return apiFetch(path, { method: opts.method, headers: opts.headers }, retries + 1);
                        });
                    }
                    return r.text().then(function(t) { throw new Error(r.status + ': ' + (t ? t.slice(0,150) : r.statusText)); });
                }
                return r.json();
            }).catch(function(e) {
                if (t) clearTimeout(t);
                if (retries < 1 && (e.message.indexOf('400') >= 0 || e.message.indexOf('Failed') >= 0 || e.name === 'AbortError')) {
                    return new Promise(function(res) { setTimeout(res, 1500); }).then(function() {
                        return apiFetch(path, { method: opts.method, headers: opts.headers }, retries + 1);
                    });
                }
                throw e;
            });
        }
        function escapeHtml(s) {
            if (!s) return '';
            var d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }
        function refreshPositions() {
            document.getElementById('positions-container').innerHTML = '<div class="empty-state">加载中...</div>';
            apiFetch('/api/positions')
                .then(function(data) {
                    var container = document.getElementById('positions-container');
                    if (data.error) {
                        container.innerHTML = '<div class="empty-state status-err">' + escapeHtml(data.error) + '</div>';
                        return;
                    }
                    var positions = data.positions || [];
                    if (positions.length === 0) {
                        container.innerHTML = '<div class="empty-state">当前无持仓</div>';
                        return;
                    }
                    var html = '<table class="positions-table"><thead><tr>' +
                        '<th>币种</th><th>方向</th><th>数量</th><th>开仓价</th><th>标记价</th>' +
                        '<th>未实现盈亏</th><th>杠杆</th><th>操作</th></tr></thead><tbody>';
                    positions.forEach(function(p) {
                        var pnlClass = (p.unrealized_pnl || 0) >= 0 ? 'pnl-positive' : 'pnl-negative';
                        html += '<tr><td>' + escapeHtml(p.symbol) + '</td><td>' + escapeHtml(p.direction) + '</td>' +
                            '<td>' + p.size + '</td><td>' + p.entry_price + '</td><td>' + p.mark_price + '</td>' +
                            '<td class="' + pnlClass + '">' + (p.unrealized_pnl || 0).toFixed(2) + ' USDT</td>' +
                            '<td>' + p.leverage + 'x</td>' +
                            '<td><button class="btn btn-close" data-symbol="' + escapeHtml(p.symbol) + '">关单</button></td></tr>';
                    });
                    html += '</tbody></table>';
                    container.innerHTML = html;
                    container.querySelectorAll('.btn-close').forEach(function(btn) {
                        btn.onclick = function() { closePosition(btn.dataset.symbol); };
                    });
                })
                .catch(function(e) {
                    document.getElementById('positions-container').innerHTML =
                        '<div class="empty-state status-err">请求失败: ' + escapeHtml(e.message) + '</div>';
                });
        }

        function closePosition(symbol) {
            if (!confirm('确定要平仓 ' + symbol + ' 吗？')) return;
            apiFetch('/api/positions/' + encodeURIComponent(symbol) + '/close', { method: 'POST', headers: {'Content-Type': 'application/json'} })
                .then(function(data) {
                    if (data.success) {
                        alert('平仓成功');
                        refreshPositions();
                    } else {
                        alert('平仓失败: ' + (data.error || '未知错误'));
                    }
                })
                .catch(e => alert('请求失败: ' + e.message));
        }

        var currentLogType = 'bot';
        var logCatalog = [];
        function _catalogItem(id) {
            return logCatalog.filter(function(x) { return x.id === id; })[0];
        }
        function syncLogTypeButtons() {
            function paintFixed(id, el) {
                if (!el) return;
                var lid = el.getAttribute('data-log-id');
                var info = _catalogItem(lid);
                el.classList.toggle('active', currentLogType === lid);
                el.classList.toggle('missing', info ? !info.exists : false);
                el.title = info ? (info.path + (info.exists ? '' : '（文件不存在）')) : '';
            }
            paintFixed('btn-log-bot', document.getElementById('btn-log-bot'));
            paintFixed('btn-log-decisions', document.getElementById('btn-log-decisions'));
            var extraWrap = document.getElementById('log-type-extra-btns');
            var sep = document.getElementById('log-extra-sep');
            if (!extraWrap) return;
            extraWrap.innerHTML = '';
            var extras = logCatalog.filter(function(x) { return x.id !== 'bot' && x.id !== 'decisions'; });
            if (sep) {
                sep.classList.toggle('visible', extras.length > 0);
            }
            extras.forEach(function(item) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'btn log-type-btn' + (currentLogType === item.id ? ' active' : '') + (!item.exists ? ' missing' : '');
                var shortLabel = (item.label || item.id).replace(/^文件:\\s*/, '');
                b.textContent = shortLabel;
                b.title = item.path + (item.exists ? '' : '（文件不存在）');
                b.onclick = function() { setLogType(item.id); };
                extraWrap.appendChild(b);
            });
        }
        function updateLogPathHint() {
            var hint = document.getElementById('log-path-hint');
            if (!hint) return;
            var cur = logCatalog.filter(function(x) { return x.id === currentLogType; })[0];
            hint.textContent = cur ? ('路径: ' + cur.path) : '';
        }
        function loadLogCatalog() {
            return apiFetch('/api/logs/catalog')
                .then(function(data) {
                    logCatalog = data.logs || [];
                    if (logCatalog.length && !logCatalog.some(function(x) { return x.id === currentLogType; })) {
                        currentLogType = logCatalog[0].id;
                    }
                    syncLogTypeButtons();
                    updateLogPathHint();
                })
                .catch(function() {
                    logCatalog = [{ id: 'bot', label: '运行日志', path: '', exists: false }];
                    syncLogTypeButtons();
                    updateLogPathHint();
                });
        }
        function fetchLogContent() {
            document.getElementById('log-container').textContent = '加载中...';
            return apiFetch('/api/logs?lines=500&type=' + encodeURIComponent(currentLogType))
                .then(function(data) {
                    var container = document.getElementById('log-container');
                    container.textContent = data.error || data.content || '（空）';
                    container.scrollTop = container.scrollHeight;
                })
                .catch(function(e) {
                    document.getElementById('log-container').textContent = '加载失败: ' + escapeHtml(e.message);
                });
        }
        function refreshLogs() {
            fetchLogContent();
        }
        function refreshLogsFull() {
            loadLogCatalog().then(fetchLogContent);
        }
        function setLogType(type) {
            currentLogType = type;
            syncLogTypeButtons();
            updateLogPathHint();
            fetchLogContent();
        }
        document.getElementById('btn-log-bot').onclick = function() { setLogType('bot'); };
        document.getElementById('btn-log-decisions').onclick = function() { setLogType('decisions'); };

        function checkStatus() {
            var el = document.getElementById('status-output');
            el.style.display = 'block';
            el.textContent = '检查中...';
            apiFetch('/api/status').then(function(d) {
                el.textContent = JSON.stringify(d, null, 2);
            }).catch(function(e) {
                el.textContent = '诊断失败: ' + e.message;
            });
        }
        document.getElementById('btn-refresh-positions').onclick = refreshPositions;
        document.getElementById('btn-refresh-logs').onclick = refreshLogsFull;
        document.getElementById('btn-check-status').onclick = checkStatus;
        var apiKeyInput = document.getElementById('api-key-input');
        apiKeyInput.value = localStorage.getItem('dashboard_api_key') || '';
        apiKeyInput.onchange = function() {
            localStorage.setItem('dashboard_api_key', apiKeyInput.value || '');
        };
        refreshPositions();
        loadLogCatalog().then(fetchLogContent);

        var posIntervalId = null;
        var logIntervalId = null;
        function getRefreshSeconds() {
            var v = parseInt(document.getElementById('auto-refresh-freq').value, 10);
            return isNaN(v) || v < 5 ? 10 : Math.min(300, v);
        }
        function startAutoRefresh() {
            stopAutoRefresh();
            var sec = getRefreshSeconds() * 1000;
            posIntervalId = setInterval(refreshPositions, sec);
            logIntervalId = setInterval(refreshLogs, sec);
        }
        function stopAutoRefresh() {
            if (posIntervalId) { clearInterval(posIntervalId); posIntervalId = null; }
            if (logIntervalId) { clearInterval(logIntervalId); logIntervalId = null; }
        }
        function updateAutoRefresh() {
            var enabled = document.getElementById('auto-refresh-switch').checked;
            document.getElementById('auto-refresh-freq').disabled = !enabled;
            if (enabled) startAutoRefresh();
            else stopAutoRefresh();
        }
        document.getElementById('auto-refresh-switch').onchange = updateAutoRefresh;
        document.getElementById('auto-refresh-freq').onchange = function() {
            if (document.getElementById('auto-refresh-switch').checked) startAutoRefresh();
        };
        document.getElementById('auto-refresh-freq').oninput = document.getElementById('auto-refresh-freq').onchange;
        updateAutoRefresh();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/favicon.ico")
def favicon():
    """避免 404：返回空响应"""
    from flask import Response
    return Response(status=204)


@app.route("/api/health")
def api_health():
    """负载均衡/探活，无需鉴权"""
    return jsonify({"status": "ok"})


@app.route("/api/logs/catalog")
def api_logs_catalog():
    """返回可切换查看的日志列表（含 logs 目录下额外 *.log）"""
    return jsonify({"logs": get_log_catalog()})


@app.route("/api/status")
def api_status():
    """调试接口：检查日志路径、持仓 API 是否正常"""
    log_info = {item["id"]: {"path": item["path"], "exists": item["exists"]} for item in get_log_catalog()}
    try:
        pm = get_position_manager()
        pm.get_position_summary()
        positions_status = "ok"
    except Exception as e:
        positions_status = str(e)
    return jsonify({
        "logs": log_info,
        "positions_api": positions_status,
    })


@app.route("/api/logs")
def api_logs():
    lines = request.args.get("lines", 500, type=int)
    lines = min(max(lines, 1), 5000)
    log_type = (request.args.get("type") or "bot").strip()
    allowed = {c["id"] for c in get_log_catalog()}
    if log_type not in allowed:
        log_type = "bot" if "bot" in allowed else (next(iter(allowed)) if allowed else "bot")
    content = read_log_tail(lines, log_type)
    return jsonify({"content": content, "type": log_type})


@app.route("/api/positions")
def api_positions():
    try:
        pm = get_position_manager()
        summary = pm.get_position_summary()
        return jsonify({
            "positions": summary.get("positions", []),
            "total_unrealized_pnl": summary.get("total_unrealized_pnl", 0),
            "position_count": summary.get("position_count", 0)
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/positions/<symbol>/close", methods=["POST"])
def api_close_position(symbol):
    try:
        pm = get_position_manager()
        result = pm.close_position(symbol)
        if result:
            return jsonify({"success": True, "message": f"{symbol} 平仓成功"})
        return jsonify({"success": False, "error": "平仓失败或该币种无持仓"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def run_dashboard(host="0.0.0.0", port=5000):
    """启动控制面板。优先使用 waitress（生产级），避免 nohup 后台运行时进程退出"""
    print(f"🌐 控制面板: http://{host}:{port}")
    if not _dashboard_api_key:
        raise RuntimeError("必须设置 DASHBOARD_API_KEY 才能启动 Dashboard（/api/health 除外接口需要鉴权）")
    if not _allowed_origins:
        raise RuntimeError("必须设置 DASHBOARD_ALLOWED_ORIGINS 才能启动 Dashboard（生产强制 CORS 白名单）")
    print("✅ 已启用 DASHBOARD_API_KEY 鉴权（/api/health 除外）")
    print(f"✅ 已启用 CORS 白名单: {', '.join(_allowed_origins)}")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=4)
    except ImportError:
        app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=5000, help="端口")
    args = parser.parse_args()
    run_dashboard(host=args.host, port=args.port)
