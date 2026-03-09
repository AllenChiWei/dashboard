"""
Agent configuration defaults.
All prompts and model settings live here so they can be adjusted without
touching the Streamlit pages or analyst logic.
"""

from datetime import datetime

# ── Model ─────────────────────────────────────────────────────────────────────
MODEL = "claude-opus-4-6"
MAX_TOKENS = 2048

# ── Thinking ──────────────────────────────────────────────────────────────────
# Adaptive thinking lets the model decide how much internal reasoning to spend.
THINKING = {"type": "adaptive"}

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """\
你是一位專業的量化交易顧問與市場分析師，專精於台灣與美國股市。
你的核心職責是根據即時恐慌指標，提供客觀、深入的市場情緒分析。

【分析框架】
1. 整合四大指標（US VIX、TW VIX、CNN Fear & Greed、大盤融資維持率）做出綜合判斷
2. 說明各指標之間的關聯性與矛盾點
3. 對比歷史常態區間，判斷當前市場位置
4. 點出潛在風險與值得關注的訊號

【輸出原則】
- 語言：繁體中文，專業但易懂
- 不給具體個股買賣建議，強調風險管理
- 數據優先，不做主觀臆測
- 遇到指標矛盾時，提供平衡觀點

【指標參考區間】
- US VIX: <15 極低波動 | 15-20 低波動 | 20-30 中等恐慌 | >30 高恐慌 | >40 極度恐慌
- TW VIX: <20 低 | 20-30 中 | >30 高恐慌
- Fear & Greed: 0-25 極度恐慌 | 25-45 恐慌 | 45-55 中性 | 55-75 貪婪 | 75-100 極度貪婪
- 融資維持率: <130% 極度恐慌（強制回補風險）| 130-166% 正常 | >166% 市場樂觀

當前分析時間：{timestamp}
"""


def get_system_prompt() -> str:
    """Return system prompt with current timestamp."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
    )


# ── Auto-Analysis Prompt ──────────────────────────────────────────────────────
AUTO_ANALYSIS_TEMPLATE = """\
以下是當前即時市場恐慌指標，請進行全面分析：

┌─────────────────────────────────────────────┐
│  綜合恐慌指數  {fear_score}/100  [{fear_label}]         │
├─────────────────────────────────────────────┤
│  US VIX（美股波動率）  : {vix}              │
│  TW VIX（台指波動率）  : {tw_vix}           │
│  CNN Fear & Greed      : {fg} ({fg_desc})   │
│  大盤融資維持率        : {margin}%          │
└─────────────────────────────────────────────┘

請依序說明：
1. **整體市場情緒**：綜合四大指標給出一句話結論
2. **指標解讀**：逐一分析每個指標的含義及異常點
3. **指標交叉驗證**：指標間是否一致？若有矛盾，如何解讀？
4. **風險提示**：目前最需要警惕的風險因子
5. **歷史對比**：這樣的組合在歷史上通常意味著什麼？
"""


def build_auto_prompt(context: dict) -> str:
    """Build the automatic analysis prompt from market context dict."""
    return AUTO_ANALYSIS_TEMPLATE.format(
        fear_score=context.get("fear_score", "N/A"),
        fear_label=context.get("fear_label", "N/A"),
        vix=context.get("vix", "N/A"),
        tw_vix=context.get("tw_vix", "N/A"),
        fg=context.get("fg", "N/A"),
        fg_desc=context.get("fg_desc", ""),
        margin=context.get("margin", "N/A"),
    )
