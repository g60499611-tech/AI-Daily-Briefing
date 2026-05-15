# 🤖 AI 每日简报推送

> 每日自动搜索全球 AI 新闻 → LLM 去重分类总结 → 精美 HTML 邮件推送至你的邮箱
>
> ## ✨ 功能亮点

- **🌐 全网智能检索** — 4 个关键词覆盖技术突破、产业供应链、商业落地、政策监管
- **🧠 LLM 智能处理** — DeepSeek 语义去重、来源白名单过滤、自动分类、核心总结
- **🎨 精美 HTML 邮件** — 苹果风格极简设计，圆角卡片布局，响应式适配手机/电脑
- **📖 名词释义库** — 自动提取 AI 专业名词并附通俗解释
- **⏰ 定时推送** — 每日北京时间 20:00 自动发送
- 
- ## 📁 项目结构

```
AI-Daily-Agent/
├── .github/workflows/
│   └── daily_report.yml      # GitHub Actions 定时任务（每日20:00）
├── src/graphs/
│   ├── state.py              # 状态定义（全局状态、节点出入参）
│   ├── graph.py              # 主图编排（5个节点的线性流程）
│   └── nodes/
│       ├── search_news_node.py     # 节点1: AI新闻搜索
│       ├── process_news_node.py    # 节点2: LLM处理（去重/分类/总结）
│       ├── generate_html_node.py   # 节点3: 生成HTML邮件
│       ├── send_email_node.py      # 节点4: 发送邮件
│       └── format_output_node.py   # 节点5: 格式化输出
├── config/
│   └── process_news_llm_cfg.json   # LLM模型配置（DeepSeek V3）
├── main.py                  # 🚀 GitHub Actions 独立运行脚本
├── requirements-gh.txt      # GitHub Actions 依赖（仅需 requests）
├── requirements.txt         # Coze 环境依赖
└── AGENTS.md                # 项目索引文档


### 搜索关键词

1. `AI 技术突破 模型迭代 算法创新 24h`
2. `AI 算力 芯片 供应链 产能 24h`
3. `AI 融资 产品发布 商业落地 大厂动态 24h`
4. `AI 政策 监管 安全伦理 治理 24h`

### 来源白名单

机器之心、36氪、新智元、央视网、新华网、TechCrunch、The Verge、斯坦福HAI、OpenAI博客

## 📧 邮件效果预览

邮件采用 **苹果风格极简设计**，包含：

- **🌐 24小时全球AI行业总览** — 顶部渐变卡片
- **🔬 技术突破** — 紫色主题卡片
- **🏭 产业供应链** — 蓝色主题卡片
- **💼 商业落地** — 绿色主题卡片
- **📜 政策监管** — 橙色主题卡片
- **📖 名词释义库** — 底部虚线分隔
