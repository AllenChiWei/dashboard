# Financial Dashboard - 執行指南

## 📋 項目完成進度

### ✅ 已完成功能

1. **爬蟲模塊**
   - ✅ VIX爬蟲 (US VIX + Taiwan TVIX)
   - ✅ 台股融資維持率爬蟲 (TWSE)
   - ✅ Fear & Greed爬蟲 (CNN)
   - ✅ Yahoo Finance爬蟲 (股票數據)

2. **數據庫**
   - ✅ MarketData表 (股票歷史數據)
   - ✅ SentimentData表 (Fear & Greed指數)
   - ✅ VIXData表 (VIX/TVIX數據)
   - ✅ MarginData表 (台股融資維持率)

3. **ETL Pipeline**
   - ✅ run_etl() - 股票數據
   - ✅ run_sentiment_etl() - Fear & Greed
   - ✅ run_vix_etl() - VIX數據
   - ✅ run_margin_etl() - 融資維持率
   - ✅ run_all_etl() - 全量爬蟲

4. **Dashboard**
   - ✅ Home頁面 - 系統概觀
   - ✅ Market Overview - 股票分析 + 技術指標
   - ✅ Financial Indicators - 所有指標展示

## 🚀 快速開始

### 1. 環境設置

```bash
# 複製.env配置
cp .env.example .env

# 安裝依賴
pip install -r requirements.txt
```

### 2. 啟動PostgreSQL數據庫

使用Docker Compose (推薦):

```bash
docker-compose up -d
```

或使用現有的PostgreSQL實例，修改.env配置

### 3. 測試爬蟲

```bash
# 運行全量測試
python test_crawlers.py

# 或手動測試
python -m pytest test_crawlers.py -v
```

### 4. 運行ETL Pipeline

```bash
# 方法1: 運行所有ETL
python -c "from src.etl.pipeline import run_all_etl; run_all_etl()"

# 方法2: 只運行特定ETL
python -c "from src.etl.pipeline import run_vix_etl; run_vix_etl()"

# 方法3: 作為模塊導入
from src.etl.pipeline import run_all_etl
run_all_etl(symbols=['2330.TW', '0050.TW', 'AAPL'])
```

### 5. 啟動Dashboard

```bash
streamlit run src/dashboard/Home.py
```

訪問 `http://localhost:8501`

## 📊 數據流程

```
爬蟲模塊
├── VIXCrawler (vix_crawler.py)
├── TaiwanMaginCrawler (taiwan_margin_crawler.py)
├── FearGreedCrawler (fear_greed_crawler.py)
└── YahooCrawler (yahoo_crawler.py)
        ↓
    ETL Pipeline (pipeline.py)
    ├── run_vix_etl()
    ├── run_margin_etl()
    ├── run_sentiment_etl()
    └── run_etl()
        ↓
    PostgreSQL數據庫
    ├── vix_data
    ├── margin_data
    ├── sentiment_data
    └── market_data
        ↓
    Dashboard (Streamlit)
    ├── Home.py (系統概觀)
    ├── pages/1_Market_Overview.py (股票分析)
    └── pages/2_Financial_Indicators.py (所有指標)
```

## 🔧 API與數據源

### 爬蟲詳細信息

| 爬蟲               | 數據源           | 更新頻率 | 備註                            |
| ------------------ | ---------------- | -------- | ------------------------------- |
| VIXCrawler         | Yahoo Finance    | 實時     | US VIX & Taiwan TVIX (0050代理) |
| TaiwanMaginCrawler | TWSE官方API      | 每日     | 台灣股票交易所                  |
| FearGreedCrawler   | CNN Fear & Greed | 每日     | fear-and-greed Python包         |
| YahooCrawler       | Yahoo Finance    | 實時     | 支持全球股票符號                |

### 數據庫架構

**VIXData表:**

```sql
- index_name: 'vix' 或 'tvix'
- date: 日期
- value: 指數值
- status: 'low' / 'medium' / 'high'
```

**MarginData表:**

```sql
- market: 'taiwan'
- date: 日期
- margin_maintenance_rate: 維持率 (%)
- status: 'low_risk' / 'medium_risk' / 'high_risk'
```

**SentimentData表:**

```sql
- name: 'fear_and_greed'
- date: 日期
- value: 指數值 (0-100)
- status: 'fear' / 'neutral' / 'greed'
```

## 📈 使用示例

### Python中使用爬蟲

```python
from src.crawlers.vix_crawler import VIXCrawler
from datetime import date, timedelta

# 創建爬蟲實例
crawler = VIXCrawler()

# 獲取US VIX數據
df = crawler.fetch_data(
    symbol='vix',
    start_date=date.today() - timedelta(days=30),
    end_date=date.today()
)

print(df)
```

### 定時更新數據

```python
import schedule
import time
from src.etl.pipeline import run_all_etl

# 每天凌晨2點運行
schedule.every().day.at("02:00").do(run_all_etl)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 🐛 故障排查

### 數據庫連接失敗

- 確保PostgreSQL已啟動
- 檢查.env中的數據庫配置
- 驗證網絡連接

### 爬蟲無數據返回

- 檢查網絡連接
- 驗證數據源是否可用
- 查看日誌信息: `logs/`目錄

### Dashboard無法訪問

- 確保Streamlit已安裝: `pip install streamlit`
- 檢查端口8501是否佔用
- 嘗試: `streamlit run src/dashboard/Home.py --logger.level=debug`

## 📚 文件結構說明

```
src/
├── crawlers/              # 爬蟲模塊
│   ├── base.py           # 基類
│   ├── vix_crawler.py    # VIX爬蟲
│   ├── taiwan_margin_crawler.py  # 融資維持率
│   ├── fear_greed_crawler.py     # Fear & Greed
│   └── yahoo_crawler.py  # Yahoo Finance
├── database/              # 數據庫
│   ├── connection.py     # 連接配置
│   └── models.py         # 數據模型
├── etl/                   # ETL流程
│   └── pipeline.py       # 主Pipeline
├── dashboard/             # Streamlit應用
│   ├── Home.py           # 主頁
│   └── pages/            # 子頁面
├── utils/                 # 工具函數
│   └── logger.py         # 日誌配置
└── config.py             # 全局配置
```

## 📝 下一步優化建議

1. **自動化調度**
   - 實現定時任務（Airflow或APScheduler）
   - 配置CI/CD自動更新

2. **數據分析增強**
   - 添加技術指標計算（RSI, MACD等）
   - 實現異常檢測

3. **機器學習**
   - 趨勢預測模型
   - 異常檢測算法

4. **性能優化**
   - 數據庫索引優化
   - 緩存層（Redis）

5. **監控與告警**
   - 實時監控儀表板
   - 警報機制（超過閾值時提醒）

## 📞 技術支持

如有問題，請檢查：

1. 日誌文件 (`src/utils/logger.py`)
2. 數據庫狀態
3. 網絡連接
4. 依賴版本兼容性

---

**最後更新**: 2026-03-07
**版本**: 1.0
