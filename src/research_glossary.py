RESEARCH_GLOSSARY = {
    "one_time_items": {
        "title": "一次性 / 非經常性項目",
        "description": (
            "一次性 / 非經常性項目，是不是公司正常營運每期固定發生的收入或費用。"
            "例如 asset impairment（資產減損）、restructuring expense（重組費用）、"
            "major disposal gain/loss（重大處分損益）、litigation settlement（訴訟和解）。"
            "這些項目可能影響某一期 EPS 或淨利，但不一定代表核心本業同步變化。"
        ),
    },
    "margin": {
        "title": "Margin（利潤率）",
        "description": (
            "Gross Margin（毛利率）觀察收入扣除銷貨成本後留下多少比例；"
            "Operating Margin（營業利益率）進一步納入營業費用；"
            "Net Margin（淨利率）則看最後轉成淨利的比例。"
            "三者合併觀察，可協助研究收入轉化為獲利的過程。"
        ),
    },
    "cash_flow": {
        "title": "Cash Flow（現金流）",
        "description": (
            "Operating Cash Flow（營業現金流）觀察核心營運產生或使用多少現金；"
            "Free Cash Flow（自由現金流）通常是在營業現金流扣除資本支出後的現金。"
            "兩者可協助研究獲利是否同步轉成現金。"
        ),
    },
    "debt": {
        "title": "Debt（負債）",
        "description": (
            "Total Debt（總負債）與 Debt to Equity（負債權益比）需要搭配 cash、cash flow、"
            "債務到期結構與產業資本結構一起理解。"
            "單一負債數字不是公司財務品質的完整結論。"
        ),
    },
    "valuation": {
        "title": "Valuation（估值）",
        "description": (
            "P/E（本益比）、Forward P/E（預估本益比）與 P/B（股價淨值比）是估值工具，"
            "用來建立比較問題與研究脈絡。它們不能單獨判定股票便宜或昂貴。"
        ),
    },
}


def get_research_glossary() -> dict[str, dict[str, str]]:
    return RESEARCH_GLOSSARY
