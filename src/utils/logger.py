"""日志工具：将 stdout/stderr 同时输出到控制台和文件"""
import os
import sys
from datetime import datetime, timezone, timedelta


class TeeOutput:
    """将输出同时写入控制台和日志文件"""
    
    def __init__(self, stream, log_path):
        self.stream = stream
        self.log_path = log_path
        self._at_line_start = True
        self._write_failed = False
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    def _timestamp_prefix(self):
        """北京时间前缀：YYYY-MM-DD HH:MM:SS"""
        beijing_tz = timezone(timedelta(hours=8))
        return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

    def _format_message(self, message):
        """为每一行增加时间前缀，并正确处理分段写入"""
        chunks = []
        for part in message.splitlines(True):
            if self._at_line_start:
                chunks.append(f"[{self._timestamp_prefix()}] ")
            chunks.append(part)
            self._at_line_start = part.endswith("\n")
        return "".join(chunks)

    def write(self, message):
        if message:
            formatted = self._format_message(message)
            self.stream.write(formatted)
            self.stream.flush()
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(formatted)
                    f.flush()
                # 文件写入恢复后，重置失败标记
                self._write_failed = False
            except (IOError, OSError):
                # 明确告警：容器 stdout 有内容但文件日志写不进去时，便于快速定位权限/挂载问题
                if not self._write_failed:
                    try:
                        sys.__stderr__.write(
                            f"[WARN] 日志文件写入失败: {self.log_path}，"
                            "请检查宿主机目录挂载与权限（如 ./logs -> /app/logs）。\n"
                        )
                        sys.__stderr__.flush()
                    except Exception:
                        pass
                    self._write_failed = True
    
    def flush(self):
        self.stream.flush()
    
    def isatty(self):
        return self.stream.isatty()


def setup_file_logging(log_path="logs/bot.log"):
    """
    设置日志输出到文件，同时保留控制台输出。
    调用后，所有 print() 和异常输出都会写入 log_path。
    """
    log_path = os.path.abspath(log_path)
    sys.stdout = TeeOutput(sys.__stdout__, log_path)
    sys.stderr = TeeOutput(sys.__stderr__, log_path)
    return log_path
