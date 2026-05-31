# 每日AI新闻推送 - GitHub Actions 独立运行脚本
"""
该脚本用于在 GitHub Actions 中独立运行，无需 Coze 环境。
通过环境变量配置 API Key 和邮箱信息。

使用方法:
    python main.py --email your@qq.com

环境变量（通过 GitHub Secrets 设置）:
    - TAVILY_API_KEY: Tavily 搜索 API Key
    - DEEPSEEK_API_KEY: DeepSeek API Key
    - SMTP_SERVER: SMTP 服务器地址（如 smtp.qq.com）
    - SMTP_PORT: SMTP 端口（如 465）
    - EMAIL_ACCOUNT: 发件人邮箱账号
    - EMAIL_AUTH_CODE: 邮箱授权码
"""
import os
import sys
import json
import argparse
import smtplib
import ssl
import time
import datetime
import logging
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================

# 搜索类别（中英文双轨，每类分别搜中文和英文）
SEARCH_CATEGORIES = [
    {
        "name": "模型与算法",
        "cn": "AI 模型 发布 开源 算法 突破",
        "en": "AI model release open-source breakthrough paper",
    },
    {
        "name": "产品与商业",
        "cn": "AI 产品发布 融资 收购 商业合作",
        "en": "AI product launch funding acquisition partnership enterprise",
    },
    {
        "name": "政策与治理",
        "cn": "AI 政策 监管 立法 安全伦理",
        "en": "AI regulation policy legislation safety ethics governance",
    },
]

# 来源白名单（三阶梯分级）
# 核心来源（直接信任，优先采用）
CORE_DOMAINS = [
    "xinhuanet.com",           # 新华网
    "people.com.cn",           # 人民网
    "caixin.com",              # 财新网
    "jiqizhixin.com",          # 机器之心
    "qbitai.com",              # 量子位
    "reuters.com",             # Reuters
    "bloomberg.com",           # Bloomberg
    "techcrunch.com",          # TechCrunch
    "theinformation.com",      # The Information
    "technologyreview.com",    # MIT Technology Review
    "arstechnica.com",         # Ars Technica
]

# 一手来源（公司官方博客/公告，直接信任）
PRIMARY_DOMAINS = [
    "openai.com",              # OpenAI
    "anthropic.com",           # Anthropic
    "mistral.ai",              # Mistral
    "ai.meta.com",             # Meta AI
    "blog.google",             # Google AI Blog
    "deepmind.google",         # DeepMind
    "blogs.microsoft.com",     # Microsoft AI Blog
]

# 补充来源（仅当核心/一手来源覆盖不足时使用）
SUPP_DOMAINS = [
    "36kr.com",                # 36氪
    "iyiou.com",               # 亿欧网
    "venturebeat.com",         # VentureBeat
    "wired.com",               # Wired
    "semianalysis.com",        # SemiAnalysis
]

# 搜索使用的所有域名（Tavily include_domains 用）
SOURCE_DOMAINS = CORE_DOMAINS + PRIMARY_DOMAINS + SUPP_DOMAINS

# 来源名称白名单（用于标题/内容匹配）
SOURCE_NAMES = [
    "新华网", "人民网", "财新网", "机器之心", "量子位",
    "Reuters", "Bloomberg", "TechCrunch", "The Information",
    "MIT Technology Review", "Ars Technica",
    "OpenAI", "Google AI", "Anthropic", "Meta AI", "Microsoft AI", "Mistral",
    "36氪", "亿欧", "VentureBeat", "Wired", "SemiAnalysis",
]

# 获取来源等级（用于 LLM 优先级判断）
def _get_source_tier(url: str) -> str:
    """返回来源等级: core / primary / supp / unknown"""
    url_lower = url.lower()
    for d in CORE_DOMAINS:
        if d in url_lower:
            return "core"
    for d in PRIMARY_DOMAINS:
        if d in url_lower:
            return "primary"
    for d in SUPP_DOMAINS:
        if d in url_lower:
            return "supp"
    return "unknown"

# ============================================================
# 步骤1: 搜索新闻（Tavily API）
# ============================================================

def search_news() -> List[Dict[str, Any]]:
    """使用 Tavily API 搜索 AI 新闻（中英文双轨）"""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.error("TAVILY_API_KEY 未设置")
        return []

    import requests

    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for cat in SEARCH_CATEGORIES:
        cat_name = cat["name"]
        # 每类搜2次:中文 + 英文
        for lang, query in [("中文", cat["cn"]), ("英文", cat["en"])]:
            try:
                logger.info(f"[{cat_name}] 搜索{lang}: {query}")
                response = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True,
                        "include_domains": SOURCE_DOMAINS,
                        "max_results": 10,
                        "time_range": "day",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                for item in results:
                    url = item.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "title": item.get("title", ""),
                            "url": url,
                            "content": item.get("content", ""),
                            "published_date": item.get("published_date", ""),
                            "keyword": query,
                            "category": cat_name,
                            "lang": lang,
                            "tier": _get_source_tier(url),
                        })

                logger.info(f"  [{cat_name}]{lang}完成，累计 {len(all_results)} 条")

            except Exception as e:
                logger.error(f"  [{cat_name}]{lang}搜索失败: {e}")
                continue

    logger.info(f"搜索完成，共 {len(all_results)} 条结果")

    # 二次过滤:按域名和名称筛选权威来源
    filtered = _filter_authoritative_sources(all_results)
    logger.info(f"来源过滤后剩余 {len(filtered)} 条权威来源结果")
    return filtered


def _filter_authoritative_sources(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按域名和名称白名单过滤权威来源（保留全部三阶梯来源）"""
    def _is_authoritative(item: Dict[str, Any]) -> bool:
        url = (item.get("url") or "").lower()
        title = (item.get("title") or "")
        content = (item.get("content") or "")
        source = (item.get("source") or "").lower()

        # 检查域名
        for domain in SOURCE_DOMAINS:
            if domain in url:
                return True

        # 检查来源名称
        for name in SOURCE_NAMES:
            if name.lower() in title.lower() or name.lower() in content.lower() or name.lower() in source:
                return True

        return False

    return [item for item in results if _is_authoritative(item)]


# ============================================================
# 步骤2: LLM处理新闻（DeepSeek API）
# ============================================================

def process_news(search_results: List[Dict[str, Any]]) -> str:
    """使用 DeepSeek API 进行去重、分类、总结，返回 JSON 字符串"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY 未设置")
        return '{"categories":[],"glossary":[],"overview":"今日暂无符合条件的AI新闻资讯。"}'

    if not search_results:
        return '{"categories":[],"glossary":[],"overview":"今日暂无符合条件的AI新闻资讯。"}'

    import requests

    # 格式化搜索结果（含来源等级）
    lines = []
    for i, item in enumerate(search_results, 1):
        tier_label = {"core": "⭐⭐核心", "primary": "⭐⭐一手", "supp": "⭐补充"}.get(item.get("tier", ""), "来源")
        lines.append(f"--- 资讯 {i} [{tier_label}] ---")
        lines.append(f"标题: {item.get('title', '')}")
        lines.append(f"链接: {item.get('url', '')}")
        lines.append(f"来源等级: {item.get('tier', 'unknown')}")
        lines.append(f"发布时间: {item.get('published_date', '')}")
        lines.append(f"所属类别: {item.get('category', '')}")
        lines.append(f"搜索语言: {item.get('lang', '')}")
        lines.append(f"内容: {item.get('content', '')}")
        lines.append("")
    search_text = "\n".join(lines)

    system_prompt = """# 角色定义
你是专业的全球AI热点资讯整理专家。你的读者是AI行业从业者，每天时间有限，需要你帮他们筛出真正值得关注的信息。像跟懂行的同事聊天一样输出，不是在写报告。

# 任务目标
处理给定的24小时内AI新闻素材，进行去重、筛选、分类，并输出**严格结构化的JSON**。

# 工作流上下文
- **Input**:包含多条AI新闻资讯的列表，每条标注了来源等级（core=核心/primary=一手/supp=补充）、所属类别、语言
- **来源选择规则（按优先级）**:
  1. **核心来源（core）**:直接信任，优先采用。包括新华社、人民网、财新网、机器之心、量子位、Reuters、Bloomberg、TechCrunch、The Information、MIT Tech Review、Ars Technica
  2. **一手来源（primary）**:公司官方博客/公告，直接信任。包括OpenAI、Google AI、Anthropic、Meta AI、Microsoft AI、Mistral等
  3. **补充来源（supp）**:仅当核心/一手来源对某个话题覆盖不足时使用。包括36氪、亿欧、VentureBeat、Wired、SemiAnalysis
  4. **不接受**:自媒体/个人号、PR通稿/软文（无独立观点、全篇引用官方说法）、内容农场/聚合平台、标题党/情绪化标题。如果发现此类内容，直接舍弃
- **Process**:
  1. **去重**:
     - 同一事件只保留1个分类入口，不要跨分类重复
     - 同一事件优先保留一手来源或最权威的报道
     - 如果同一事件有不同角度的权威报道（如:技术分析+商业影响），可各保留1篇，但需在总结中说明关联
     - 纯转载/改写一律去重，只保留原始来源
  2. **来源过滤**:按上述优先级规则选择，非白名单来源**一律剔除**，宁缺毋滥
  3. **分类**:严格按【模型与算法、产品与商业、政策与治理】3类划分
     - 不强制每个分类都输出，没有高价值资讯就跳过，不要凑数
     - **模型与算法**:AI模型能力层面的变化（新模型发布、开源项目、训练方法突破、基准测试变化）
       - 不属于此类的:纯学术小众论文、无实际影响的"理论上可能"
     - **产品与商业**:AI变成产品或产生商业行为（产品上线/更新、融资并购、商业合作、芯片算力动态）
       - 不属于此类的:纯技术论文、未商业化的研究
     - **政策与治理**:政府或机构对AI的约束/推动（立法、监管行动、安全事件、行业标准）
       - 不属于此类的:企业自律声明（归商业类）
  4. **今日信号**:从上述新闻中挑1-2条最重要的，回答"为什么这两条重要？它会带来什么变化？对谁有影响？"用2-3句话写一段判断，不是总结，是观点。如果没有真正重要的信号，signal字段留空字符串
  5. **趋势判断**:每类资讯生成 trend，不是"归纳今天出现了哪些新闻"，而是回答:
     - 这个方向最近在发生什么变化？
     - 今天的新闻是延续趋势还是出现拐点？
     - 用1-2句话说清楚，不要列点，要像跟同事聊天一样自然
  6. **整体总结**:生成全局 overview
  7. **名词提取**:提取资讯中的AI专业陌生名词，放入 glossary 列表（0-8个/天）

# 约束与规则
- **来源过滤是硬性要求**:严格执行三级来源优先级
- 每类最多输出4条，总数不超过12条
- **3个分类不强制全输出**，没有高价值资讯的分类 items 设为 []，trend 写"今日无高价值资讯"，不要凑数
- 禁止添加无关内容、不篡改资讯事实、不重复描述

# 语气要求
- 像跟懂行的同事聊天，不是在写报告
- 可以有判断，不要中立到什么都没说
- 禁止:车轱辘话、PR腔、"标志着""意味着"等空洞转折、堆砌形容词
- 每条新闻摘要2-3句话，只说它是什么、为什么值得关注

# 输出格式
**必须**返回以下JSON结构（不要包含任何markdown代码块包裹，纯JSON字符串）:
{
  "categories": [
    {
      "name": "模型与算法",
      "trend": "这个方向最近在发生什么变化...",
      "items": [
        {
          "title": "资讯标题",
          "source": "权威来源名称",
          "link": "原文完整URL",
          "summary": "2-3句话，只说什么和为什么值得关注"
        }
      ]
    }
  ],
  "signal": "从新闻中挑1-2条最重要的做的判断，2-3句话；无重要信号则留空字符串",
  "glossary": [
    {
      "term": "名词",
      "explanation": "一句话通俗解释"
    }
  ],
  "overview": "24小时全球AI行业总览总结"
}"""

    try:
        logger.info("调用 DeepSeek API 处理新闻...")
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请处理以下24小时内AI新闻素材:\n\n{search_text}"},
                ],
                "temperature": 0.1,
                "max_tokens": 8192,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        logger.info(f"LLM处理完成，输出 {len(raw_content)} 字符")

        # 解析JSON（兼容LLM用 ```json 代码块包裹的情况）
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
            if "```" in content:
                content = content.rsplit("```", 1)[0]
            content = content.strip()
        json.loads(content)  # 验证是合法JSON
        return content

    except json.JSONDecodeError as e:
        logger.error(f"LLM未返回合法JSON: {e}，原始输出前200字符: {raw_content[:200]}")
        return '{"categories":[],"glossary":[],"overview":"今日暂无符合条件的AI新闻资讯。"}'
    except Exception as e:
        logger.error(f"LLM处理失败: {e}")
        return '{"categories":[],"glossary":[],"overview":"今日暂无符合条件的AI新闻资讯。"}'


# ============================================================
# 步骤3: 生成HTML（从JSON解析，永不因格式变化失败）
# ============================================================

def generate_html(processed_news: str) -> str:
    """生成精美的HTML邮件内容（从JSON解析）"""
    if not processed_news:
        return _empty_html()

    try:
        data = json.loads(processed_news)
    except json.JSONDecodeError:
        return _empty_html()

    categories = data.get("categories", [])
    glossary = data.get("glossary", [])
    overview = data.get("overview", "")
    signal_text = data.get("signal", "")

    # 构建分类卡片
    cards_html = ""
    category_config = {
        "模型与算法": {"icon": "🧠", "color": "#5856D6"},
        "产品与商业": {"icon": "💼", "color": "#34C759"},
        "政策与治理": {"icon": "📜", "color": "#FF9500"},
    }

    for cat_entry in categories:
        cat = cat_entry.get("name", "")
        cfg = category_config.get(cat, {"icon": "📰", "color": "#007AFF"})
        items = cat_entry.get("items", [])
        trend = cat_entry.get("trend", "")

        items_html = ""
        for item in items:
            items_html += f"""
            <div style="padding:16px 0;border-bottom:1px solid #f0f0f0;">
                <div style="font-size:15px;font-weight:600;color:#1d1d1f;line-height:1.4;margin-bottom:6px;">
                    {item.get('title', '')}
                </div>
                <div style="font-size:13px;color:#86868b;margin-bottom:8px;">
                    <span style="background:#f5f5f7;padding:2px 8px;border-radius:4px;">{item.get('source', '')}</span>
                </div>
                <div style="font-size:14px;color:#515154;line-height:1.6;margin-bottom:8px;">
                    {item.get('summary', '')}
                </div>
                <a href="{item.get('link', '#')}" target="_blank" style="font-size:13px;color:#007AFF;text-decoration:none;font-weight:500;">
                    阅读原文 →
                </a>
            </div>
            """

        if not items:
            items_html = """
            <div style="padding:24px 0;text-align:center;">
                <div style="font-size:36px;margin-bottom:8px;">📭</div>
                <div style="font-size:14px;color:#86868b;">今日暂无该分类的高价值新闻</div>
            </div>
            """

        trend_html = ""
        if trend:
            trend_html = f"""
            <div style="margin-top:16px;padding:12px 16px;background:{cfg['color']}08;border-left:3px solid {cfg['color']};border-radius:6px;">
                <div style="font-size:13px;color:{cfg['color']};font-weight:600;margin-bottom:4px;">📊 本类24h核心趋势</div>
                <div style="font-size:14px;color:#515154;line-height:1.5;">{trend}</div>
            </div>
            """

        cards_html += f"""
        <div style="background:#ffffff;border-radius:16px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <div style="display:flex;align-items:center;margin-bottom:20px;padding-bottom:16px;border-bottom:2px solid {cfg['color']}20;">
                <span style="font-size:24px;margin-right:10px;">{cfg['icon']}</span>
                <h2 style="font-size:20px;font-weight:700;color:{cfg['color']};margin:0;">{cat}</h2>
            </div>
            {items_html}
            {trend_html}
        </div>
        """

    # 今日信号
    signal_html = ""
    if signal_text:
        signal_html = f"""
        <div style="background:linear-gradient(135deg,#FFD60A08,#FF950008);border-radius:16px;padding:24px;margin-bottom:20px;border:1px solid #FFD60A30;">
            <div style="display:flex;align-items:center;margin-bottom:12px;">
                <span style="font-size:24px;margin-right:10px;">📡</span>
                <h2 style="font-size:20px;font-weight:700;color:#FF9500;margin:0;">今日信号</h2>
            </div>
            <div style="font-size:14px;color:#515154;line-height:1.7;padding-left:4px;">{signal_text}</div>
        </div>
        """

    # 名词释义
    glossary_html = ""
    if glossary:
        g_items = "".join(
            f'<div style="display:flex;margin-bottom:10px;padding:8px 0;border-bottom:1px dashed #e5e5e7;">'
            f'<span style="font-size:14px;font-weight:600;color:#5856D6;min-width:120px;">{g.get("term", "")}</span>'
            f'<span style="font-size:14px;color:#515154;line-height:1.5;">{g.get("explanation", "")}</span></div>'
            for g in glossary if g.get("term")
        )
        glossary_html = f"""
        <div style="margin-top:32px;padding-top:24px;border-top:2px dashed #d2d2d7;">
            <h3 style="font-size:18px;font-weight:700;color:#1d1d1f;margin-bottom:16px;">📖 名词释义库</h3>
            {g_items}
        </div>
        """

    # 总览
    overview_html = ""
    if overview:
        overview_html = f"""
        <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:16px;padding:24px;margin-bottom:20px;">
            <div style="font-size:16px;font-weight:600;color:#ffffff;margin-bottom:8px;">🌐 24小时全球AI行业总览</div>
            <div style="font-size:14px;color:rgba(255,255,255,0.9);line-height:1.6;">{overview}</div>
        </div>
        """

    today = datetime.datetime.now().strftime("%Y年%m月%d日")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI每日简报</title></head>
<body style="margin:0;padding:0;background:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f7;">
<tr><td align="center" style="padding:20px 0;">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">
<tr><td style="padding:40px 24px 24px;text-align:center;">
<div style="font-size:32px;font-weight:800;color:#1d1d1f;letter-spacing:-0.5px;">AI 每日简报</div>
<div style="font-size:14px;color:#86868b;margin-top:6px;">{today} · 全球AI资讯精选</div>
</td></tr>
{overview_html}
<tr><td style="padding:0 0 20px;">{cards_html}</td></tr>
<tr><td style="padding:0 0 20px;">{signal_html}</td></tr>
<tr><td style="padding:0 0 20px;">{glossary_html}</td></tr>
<tr><td style="padding:24px;text-align:center;border-top:1px solid #d2d2d7;">
<div style="font-size:12px;color:#86868b;line-height:1.6;">
<p style="margin:0 0 4px;">🤖 由 AI 自动生成 · 每日 20:00 推送 · 中英文双轨搜索</p>
<p style="margin:0;">数据来源:新华网、人民网、机器之心、36氪、量子位、财新网、亿欧网、MIT Technology Review、VentureBeat、Wired、The Information、SemiAnalysis</p>
</div></td></tr>
</table></td></tr></table></body></html>"""


def _empty_html() -> str:
    today = datetime.datetime.now().strftime("%Y年%m月%d日")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI每日简报</title></head>
<body style="margin:0;padding:0;background:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f7;">
<tr><td align="center" style="padding:80px 20px;">
<table width="400" cellpadding="0" cellspacing="0">
<tr><td style="text-align:center;padding:40px;background:#ffffff;border-radius:16px;">
<div style="font-size:48px;margin-bottom:16px;">📭</div>
<div style="font-size:20px;font-weight:600;color:#1d1d1f;margin-bottom:8px;">今日暂无新闻</div>
<div style="font-size:14px;color:#86868b;">{today} 暂无符合条件的AI新闻资讯</div>
</td></tr></table></td></tr></table></body></html>"""


# ============================================================
# 步骤4: 发送邮件（SMTP）
# ============================================================

def send_email(to_addr: str, html_content: str) -> bool:
    """通过 SMTP 发送 HTML 邮件（QQ邮箱专用）"""
    smtp_server = "smtp.qq.com"
    smtp_port = 465
    account = os.environ.get("EMAIL_ACCOUNT", "")
    auth_code = os.environ.get("EMAIL_AUTH_CODE", "")

    if not all([account, auth_code]):
        logger.error("邮件配置不完整，请设置 EMAIL_ACCOUNT, EMAIL_AUTH_CODE")
        return False

    try:
        msg = MIMEText(html_content, "html", "utf-8")
        msg["From"] = formataddr(("AI每日简报", account))
        msg["To"] = to_addr
        msg["Subject"] = Header(f"AI每日简报 - {datetime.datetime.now().strftime('%Y年%m月%d日')}", "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        for i in range(3):
            try:
                with smtplib.SMTP_SSL(smtp_server, smtp_port, context=ctx, timeout=30) as server:
                    server.ehlo()
                    server.login(account, auth_code)
                    server.sendmail(account, [to_addr], msg.as_string())
                    server.quit()
                logger.info(f"邮件成功发送至 {to_addr}")
                return True
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                    smtplib.SMTPDataError, smtplib.SMTPHeloError, ssl.SSLError, OSError) as e:
                logger.warning(f"发送尝试 {i+1}/3 失败: {type(e).__name__}")
                time.sleep(1 * (i + 1))

        logger.error("邮件发送失败（重试3次后）")
        return False

    except Exception as e:
        logger.error(f"发送邮件异常: {e}")
        return False


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="AI每日新闻推送")
    parser.add_argument("--email", required=True, help="收件人QQ邮箱地址")
    parser.add_argument("--output", help="保存HTML到本地文件（可选）")
    args = parser.parse_args()

    logger.info(f"🚀 开始执行AI每日新闻推送，收件人: {args.email}")

    # 步骤1: 搜索
    logger.info("📡 步骤1/4: 搜索AI新闻...")
    results = search_news()
    logger.info(f"   共获取 {len(results)} 条结果")

    # 步骤2: LLM处理
    logger.info("🧠 步骤2/4: LLM处理新闻（去重/分类/总结）...")
    processed = process_news(results)
    logger.info(f"   处理完成，{len(processed)} 字符")

    # 步骤3: 生成HTML
    logger.info("🎨 步骤3/4: 生成HTML邮件...")
    html = generate_html(processed)
    logger.info(f"   HTML生成完成，{len(html)} 字符")

    # 保存HTML（可选）
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"   HTML已保存至: {args.output}")

    # 步骤4: 发送邮件
    logger.info("📧 步骤4/4: 发送邮件...")
    success = send_email(args.email, html)

    if success:
        logger.info("✅ AI每日新闻推送完成！")
    else:
        logger.error("❌ 邮件发送失败，请检查配置")
        sys.exit(1)


if __name__ == "__main__":
    main()
