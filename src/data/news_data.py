"""新闻与情绪数据：恐惧贪婪指数、RSS 聚合 + CryptoCompare 免费新闻 API"""
import os
import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class NewsDataManager:
    """获取新闻与市场情绪数据，供 AI 决策参考"""

    def __init__(self):
        self.rss_sources = self._load_rss_sources()
        self.keyword_map = self._load_keyword_map()
        self._fng_cache = None
        self._fng_cache_time = 0
        self._news_cache = None
        self._news_cache_time = 0
        self._news_cache_limit = None
        self._sentiment_bundle_cache = None
        self._sentiment_bundle_time = 0
        self._cache_ttl = 3600  # 1 小时缓存

    def _load_rss_sources(self):
        """加载 RSS 新闻源（环境变量可覆盖）"""
        sources = os.getenv("NEWS_RSS_SOURCES", "").strip()
        if sources:
            return [url.strip() for url in sources.split(",") if url.strip()]
        return [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
            "https://decrypt.co/feed",
        ]

    def _load_keyword_map(self):
        """加载新闻关键词分析配置，格式: key=alias1|alias2, key2=alias..."""
        raw = os.getenv("NEWS_ANALYSIS_KEYWORDS", "").strip()
        if not raw:
            return {
                "BTC": ["btc", "bitcoin"],
                "ETH": ["eth", "ethereum"],
                "SOL": ["sol", "solana"],
                "ETF": ["etf"],
                "FED": ["fed", "fomc", "interest rate"],
                "SEC": ["sec"],
                "HACK": ["hack", "exploit", "breach"],
            }
        mapping = {}
        for segment in raw.split(","):
            segment = segment.strip()
            if "=" not in segment:
                continue
            key, aliases = segment.split("=", 1)
            k = key.strip().upper()
            vals = [v.strip().lower() for v in aliases.split("|") if v.strip()]
            if k and vals:
                mapping[k] = vals
        return mapping or {"BTC": ["btc", "bitcoin"], "ETH": ["eth", "ethereum"]}

    def _parse_rss_datetime(self, value):
        if not value:
            return ""
        try:
            return parsedate_to_datetime(value).isoformat()
        except Exception:
            return value

    def _safe_text(self, node, default=""):
        if node is None or node.text is None:
            return default
        return node.text.strip()

    def get_fear_greed_index(self):
        """
        获取加密货币恐惧贪婪指数 (0-100)
        来源: https://alternative.me/crypto/fear-and-greed-index/
        免费，无需 API Key
        """
        if self._fng_cache and (time.time() - self._fng_cache_time) < self._cache_ttl:
            return self._fng_cache
        try:
            r = requests.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=10,
                headers={"User-Agent": "AI-Trading-Bot/1.0"}
            )
            data = r.json()
            items = data.get("data", [])
            if items:
                item = items[0]
                self._fng_cache = {
                    "value": int(item.get("value", 50)),
                    "classification": item.get("value_classification", "Unknown"),
                    "timestamp": item.get("timestamp", ""),
                }
                self._fng_cache_time = time.time()
                return self._fng_cache
        except Exception as e:
            print(f"获取恐惧贪婪指数失败: {e}")
        return None

    def get_rss_news(self, limit=10):
        """获取免费 RSS 新闻（无需 API Key）"""
        if (
            self._news_cache
            and self._news_cache_limit == limit
            and (time.time() - self._news_cache_time) < 600
        ):
            return self._news_cache

        all_news = []
        seen = set()
        for rss_url in self.rss_sources:
            try:
                r = requests.get(
                    rss_url,
                    timeout=12,
                    headers={"User-Agent": "AI-Trading-Bot/1.0"}
                )
                r.raise_for_status()
                root = ET.fromstring(r.content)
                # RSS 2.0: channel/item; Atom: entry
                items = root.findall(".//item")
                entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                if entries and not items:
                    for entry in entries:
                        title = self._safe_text(entry.find("{http://www.w3.org/2005/Atom}title"))
                        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
                        link = link_node.attrib.get("href", "").strip() if link_node is not None else ""
                        published = self._safe_text(entry.find("{http://www.w3.org/2005/Atom}updated"))
                        key = (title, link)
                        if title and key not in seen:
                            seen.add(key)
                            all_news.append({
                                "title": title,
                                "url": link,
                                "source": rss_url,
                                "published_at": self._parse_rss_datetime(published),
                                "positive": 0,
                                "negative": 0,
                                "important": 0,
                                "liked": 0,
                                "disliked": 0,
                            })
                else:
                    for item in items:
                        title = self._safe_text(item.find("title"))
                        link = self._safe_text(item.find("link"))
                        published = self._safe_text(item.find("pubDate"))
                        source_node = item.find("source")
                        source = self._safe_text(source_node, rss_url)
                        key = (title, link)
                        if title and key not in seen:
                            seen.add(key)
                            all_news.append({
                                "title": title,
                                "url": link,
                                "source": source,
                                "published_at": self._parse_rss_datetime(published),
                                "positive": 0,
                                "negative": 0,
                                "important": 0,
                                "liked": 0,
                                "disliked": 0,
                            })
            except Exception as e:
                print(f"RSS 获取失败 {rss_url}: {e}")

        # 简单按发布时间倒序（解析失败的放后面）
        def _sort_key(n):
            return n.get("published_at", "") or ""
        all_news.sort(key=_sort_key, reverse=True)
        self._news_cache = all_news[:limit]
        self._news_cache_limit = limit
        self._news_cache_time = time.time()
        return self._news_cache

    def get_cryptocompare_news(self, limit=10):
        """CryptoCompare 免费新闻接口（无需 API Key，有频控时请适度拉取）"""
        if limit <= 0:
            return []
        try:
            r = requests.get(
                "https://min-api.cryptocompare.com/data/v2/news/",
                params={"lang": "EN"},
                timeout=12,
                headers={"User-Agent": "AI-Trading-Bot/1.0"},
            )
            r.raise_for_status()
            payload = r.json()
            if payload.get("Response") == "Error":
                return []
            data = payload.get("Data") or []
            out = []
            for item in data[:limit]:
                ts = item.get("published_on")
                published = ""
                if isinstance(ts, (int, float)) and ts > 0:
                    published = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                src = item.get("source_info")
                src_name = "CryptoCompare"
                if isinstance(src, dict):
                    src_name = src.get("name") or src.get("img") or "CryptoCompare"
                out.append({
                    "title": (item.get("title") or "").strip(),
                    "url": (item.get("url") or "").strip(),
                    "source": src_name,
                    "published_at": published,
                    "positive": 0,
                    "negative": 0,
                    "important": 0,
                    "liked": 0,
                    "disliked": 0,
                })
            return [x for x in out if x["title"]]
        except Exception as e:
            print(f"CryptoCompare 新闻获取失败: {e}")
            return []

    def _merge_news_lists(self, *lists, dedupe_limit=30):
        """多源合并，按标题去重，保留时间较新的在前"""
        seen = set()
        merged = []
        for lst in lists:
            for item in lst or []:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                key = title.lower()[:120]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        merged.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        return merged[:dedupe_limit]

    def analyze_news(self, news_list, news_policy=None, trading_symbols=None):
        """基于标题做关键词计数 + 策略闸门用 hints（不依赖付费新闻 API）"""
        if not news_list:
            return None
        news_policy = news_policy or {}
        trading_symbols = trading_symbols or []
        counts = {k: 0 for k in self.keyword_map.keys()}
            
        # 情感分析：简单基于关键词的情感倾向评分
        positive_keywords = ['bullish', 'rally', 'surge', 'breakout', 'pump', 'moon', 'adoption', 'partnership', 'upgrade', 'innovation']
        negative_keywords = ['crash', 'dump', 'hack', 'exploit', 'ban', 'regulation', 'sec', 'lawsuit', 'scam', 'fraud', 'breach']
            
        sentiment_score = 0  # 正值表示乐观，负值表示悲观
        total_analyzed = 0
            
        for item in news_list:
            title = (item.get('title') or '').lower()
            for key, aliases in self.keyword_map.items():
                if any(alias in title for alias in aliases):
                    counts[key] += 1
                
            # 简单情感分析
            title_words = title.split()
            pos_count = sum(1 for word in title_words if any(pk in title for pk in positive_keywords))
            neg_count = sum(1 for word in title_words if any(nk in title for nk in negative_keywords))
            sentiment_score += (pos_count - neg_count)
            total_analyzed += 1
            
        # 归一化情感评分 (-1 到 1)
        normalized_sentiment = sentiment_score / max(total_analyzed, 1)
            
        top_keywords = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        top_keywords = [k for k in top_keywords if k[1] > 0][:5]
    
        hack_hits = counts.get("HACK", 0)
        macro_hits = counts.get("FED", 0) + counts.get("SEC", 0)
        risk_off_min = int(news_policy.get("risk_off_min_hack_hits", 1))
        risk_off = news_policy.get("block_open_on_risk_off", True) and hack_hits >= risk_off_min
    
        symbol_hits = {}
        for sym in trading_symbols:
            if not isinstance(sym, str):
                continue
            s = sym.upper().replace("-", "")
            if not s.endswith("USDT"):
                continue
            base = s[:-4].lower()
            aliases = {base}
            km = self.keyword_map.get(base.upper(), [])
            aliases.update(km)
            n = 0
            for item in news_list:
                t = (item.get('title') or '').lower()
                if any(a in t for a in aliases if a):
                    n += 1
            symbol_hits[sym] = n
    
        strategy_hints = {
            "risk_off": bool(risk_off),
            "hack_hits": hack_hits,
            "macro_stress_hits": macro_hits,
            "symbol_title_hits": symbol_hits,
            "sentiment_score": round(normalized_sentiment, 2),  # 新增：情感评分
            "sentiment_classification": "bullish" if normalized_sentiment > 0.2 else ("bearish" if normalized_sentiment < -0.2 else "neutral")
        }
        return {
            "total_news": len(news_list),
            "keyword_hits": counts,
            "top_keywords": top_keywords,
            "strategy_hints": strategy_hints,
        }

    def get_sentiment_summary(self, news_policy=None, trading_symbols=None):
        """
        汇总情绪数据，供 prompt 与策略闸门使用。
        news_policy / trading_symbols 来自 trading_config.json 的 news 段与 trading.symbols。
        """
        news_policy = news_policy or {}
        trading_symbols = trading_symbols or []
        if (
            self._sentiment_bundle_cache
            and (time.time() - self._sentiment_bundle_time) < 600
        ):
            return self._sentiment_bundle_cache

        summary = {}
        fng = self.get_fear_greed_index()
        if fng:
            summary["fear_greed"] = fng

        rss_n = int(news_policy.get("rss_fetch_count", 12))
        rss = self.get_rss_news(limit=max(rss_n, 5))

        if news_policy.get("cryptocompare_enabled", True):
            cc_n = int(news_policy.get("cryptocompare_limit", 8))
            cc = self.get_cryptocompare_news(limit=cc_n)
            merged = self._merge_news_lists(rss, cc, dedupe_limit=max(rss_n + cc_n, 20))
        else:
            merged = list(rss)

        prompt_news_n = int(news_policy.get("prompt_headlines", 5))
        if merged:
            summary["news"] = merged[:prompt_news_n]
            analysis = self.analyze_news(merged, news_policy, trading_symbols)
            if analysis:
                summary["news_analysis"] = analysis

        result = summary if summary else None
        self._sentiment_bundle_cache = result
        self._sentiment_bundle_time = time.time()
        return result
