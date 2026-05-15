# 每日AI新闻推送 - GitHub Actions 独立运行脚本
"""
该脚本用于在 GitHub Actions 中独立运行，无需 Coze 环境。
通过环境变量配置 API Key 和邮箱信息。

使用方法：
    python main.py --email your@qq.com

环境变量（通过 GitHub Secrets 设置）：
    - TAVILY_API_KEY: Tavily 搜索 API Key
    - DEEPSEEK_API_KEY: DeepSeek API Key
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

# 搜索关键词（固定4个）
SEARCH_KEYWORDS = [
    "AI 技术突破 模型迭代 算法创新",
    "AI 算力 芯片 供应链 产能",
    "AI 融资 产品发布 商业落地 大厂动态",
    "AI 政策 监管 安全伦理 治理",
]

# 来源白名单
SOURCE_WHITELIST = [
    "机器之心", "36氪", "新智元", "央视网", "新华网",
    "TechCrunch", "The Verge", "斯坦福HAI", "OpenAI博客",
    "机器之心", "36氪", "新智元",
]

# ============================================================
# 步骤1: 搜索新闻（Tavily API）
# ============================================================

def search_news() -> List[Dict[str, Any]]:
    """使用 Tavily API 搜索 AI 新闻"""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.error("TAVILY_API_KEY 未设置")
        return []

    import requests

    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for keyword in SEARCH_KEYWORDS:
        try:
            logger.info(f"搜索关键词: {keyword}")
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": keyword,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_domains": [],
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
                        "keyword": keyword,
                    })

            logger.info(f"关键词 '{keyword}' 完成，累计 {len(all_results)} 条")

        except Exception as e:
            logger.error(f"搜索 '{keyword}' 失败: {e}")
            continue

    logger.info(f"搜索完成，共 {len(all_results)} 条结果")
    return all_results


# ============================================================
# 步骤2: LLM处理新闻（DeepSeek API）
# ============================================================

def process_news(search_results: List[Dict[str, Any]]) -> str:
    """使用 DeepSeek API 进行去重、分类、总结"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY 未设置")
        return "今日暂无符合条件的AI新闻资讯。"

    if not search_results:
        return "今日暂无符合条件的AI新闻资讯。"

    import requests

    # 格式化搜索结果
    lines = []
    for i, item in enumerate(search_results, 1):
        lines.append(f"--- 资讯 {i} ---")
        lines.append(f"标题: {item.get('title', '')}")
        lines.append(f"链接: {item.get('url', '')}")
        lines.append(f"发布时间: {item.get('published_date', '')}")
        lines.append(f"内容: {item.get('content', '')}")
        lines.append(f"搜索关键词: {item.get('keyword', '')}")
        lines.append("")
    search_text = "\n".join(lines)

    system_prompt = """# 角色定义
你是专业的全球AI热点资讯整理专家，拥有出色的信息去重、分类和总结能力。

# 任务目标
处理给定的24小时内AI新闻素材，进行去重、来源过滤、分类整理，并输出结构化结果。

# 工作流上下文
- **Input**：包含多条AI新闻资讯的列表
- **Process**：
  1. **去重**：判断多条资讯是否为同一热点，同一热点仅保留1篇最权威来源
  2. **来源过滤**：仅保留【机器之心、36氪、新智元、央视网、新华网、TechCrunch、The Verge、斯坦福HAI、OpenAI博客】来源，其余直接剔除
  3. **分类**：严格按【技术突破、产业供应链、商业落地、政策监管】4类划分
  4. **输出格式**：每篇资讯固定格式「标题｜权威来源｜原文链接｜一段话50-150字核心总结」
  5. **名词提取**：提取资讯中的AI专业陌生名词，文末附「名词释义库」
  6. **整体总结**：每类资讯结束后加「本类24h核心趋势总结」；最后加「24小时全球AI行业总览总结」

# 约束与规则
- 每类最多输出3条，总数不超过12条
- 名词释义0-8个/天
- 禁止添加无关内容、不篡改资讯事实、不重复描述
- 格式统一整洁

# 输出格式
严格按以下格式输出：

## 🔬 技术突破
标题｜来源｜链接｜核心总结
...

## 🏭 产业供应链
...

## 💼 商业落地
...

## 📜 政策监管
...

## 📖 名词释义库
【名词1】：一句话通俗解释"""

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
                    {"role": "user", "content": f"请处理以下24小时内AI新闻素材：\n\n{search_text}"},
                ],
                "temperature": 0.1,
                "max_tokens": 8192,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logger.info(f"LLM处理完成，输出 {len(content)} 字符")
        return content

    except Exception as e:
        logger.error(f"LLM处理失败: {e}")
        return "今日暂无符合条件的AI新闻资讯。"


# ============================================================
# 步骤3: 生成HTML
# ============================================================

def generate_html(processed_news: str) -> str:
    """生成精美的HTML邮件内容"""
    if not processed_news or processed_news == "今日暂无符合条件的AI新闻资讯。":
        return _empty_html()

    sections = _parse_sections(processed_news)
    glossary = _parse_glossary(processed_news)
    overview = _parse_overview(processed_news)

    # 构建分类卡片
    cards_html = ""
    category_config = {
        "技术突破": {"icon": "🔬", "color": "#5856D6"},
        "产业供应链": {"icon": "🏭", "color": "#007AFF"},
        "商业落地": {"icon": "💼", "color": "#34C759"},
        "政策监管": {"icon": "📜", "color": "#FF9500"},
    }

    for section in sections:
        cat = section.get("category", "")
        cfg = category_config.get(cat, {"icon": "📰", "color": "#007AFF"})
        items = section.get("items", [])
        trend = section.get("trend", "")

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

    # 名词释义
    glossary_html = ""
    if glossary:
        g_items = "".join(
            f'<div style="display:flex;margin-bottom:10px;padding:8px 0;border-bottom:1px dashed #e5e5e7;">'
            f'<span style="font-size:14px;font-weight:600;color:#5856D6;min-width:120px;">{t}</span>'
            f'<span style="font-size:14px;color:#515154;line-height:1.5;">{d}</span></div>'
            for t, d in glossary
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
<tr><td style="padding:0 0 20px;">{glossary_html}</td></tr>
<tr><td style="padding:24px;text-align:center;border-top:1px solid #d2d2d7;">
<div style="font-size:12px;color:#86868b;line-height:1.6;">
<p style="margin:0 0 4px;">🤖 由 AI 自动生成 · 每日 20:00 推送</p>
<p style="margin:0;">数据来源：机器之心、36氪、新智元、TechCrunch、The Verge 等</p>
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


def _parse_sections(text: str) -> list:
    sections, current_cat, current_items, current_trend = [], None, [], ""
    cats = ["技术突破", "产业供应链", "商业落地", "政策监管"]
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for cat in cats:
            if cat in line and ("##" in line or "🔬" in line or "🏭" in line or "💼" in line or "📜" in line):
                if current_cat and current_items:
                    sections.append({"category": current_cat, "items": current_items, "trend": current_trend})
                current_cat, current_items, current_trend = cat, [], ""
                break
        else:
            if "本类24h核心趋势" in line:
                current_trend = line.split("】", 1)[-1].strip() if "】" in line else line
                continue
            if "｜" in line and not line.startswith("【") and not line.startswith("##"):
                parts = line.split("｜")
                if len(parts) >= 4:
                    current_items.append({"title": parts[0].strip(), "source": parts[1].strip(), "link": parts[2].strip(), "summary": "｜".join(parts[3:]).strip()})
    if current_cat and current_items:
        sections.append({"category": current_cat, "items": current_items, "trend": current_trend})
    return sections


def _parse_glossary(text: str) -> list:
    glossary, in_g = [], False
    for line in text.split("\n"):
        line = line.strip()
        if "名词释义库" in line:
            in_g = True
            continue
        if in_g and line.startswith("【") and "】" in line:
            t = line[line.find("【") + 1:line.find("】")]
            d = line[line.find("】") + 1:].strip()
            if t and d:
                glossary.append((f"【{t}】", d))
    return glossary


def _parse_overview(text: str) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if "24小时全球AI行业总览总结" in line or "全球AI行业总览" in line:
            return line.split("】", 1)[-1].strip() if "】" in line else line
    return ""


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
