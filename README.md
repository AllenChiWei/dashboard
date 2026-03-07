# Financial AI Dashboard 📈

Production-grade financial data dashboard system with automated ETL, PostgreSQL storage, and AI-ready architecture.

## 🚀 Features
- **Automated Crawler**: Fetches daily market data (Yahoo Finance Default).
- **PostgreSQL Database**: Robust storage with deduplication logic.
- **Interactive Dashboard**: Streamlit-based UI for market analysis.
- **Dockerized**: Easy deployment with Docker Compose.
- **CI/CD**: GitHub Actions for daily automated data updates.

## 🛠 Project Structure
```
financial_dashboard/
├── src/
│   ├── database/    # Database models & connection
│   ├── crawlers/    # Data fetching modules (Extensible)
│   ├── etl/         # Data pipeline & transformation
│   └── dashboard/   # Streamlit application
├── config.py        # Configuration management
├── docker-compose.yml
└── requirements.txt
```

## ⚙️ Setup & Installation

### 1. Environment Configuration
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

**Required Credentials:**
- **Database**: You need a running PostgreSQL instance.
    - If using Docker Compose (Recommended), the default values in `.env.example` work out of the box.
    - If using a cloud database (e.g., AWS RDS, Neon, Supabase), you need:
        - `POSTGRES_HOST`
        - `POSTGRES_USER`
        - `POSTGRES_PASSWORD`
        - `POSTGRES_DB`

### 2. Run with Docker (Recommended)
```bash
docker-compose up --build
```
- Dashboard Access: `http://localhost:8501`
- Database: `localhost:5432`

### 3. Run Manually
Install dependencies:
```bash
pip install -r requirements.txt
```

Run the Dashboard:
```bash
streamlit run src/dashboard/Home.py
```

Run ETL Pipeline manually:
```bash
python src/etl/pipeline.py
```

## 🤖 GitHub Actions Setup
To enable daily automatic updates:
1. Push this repository to GitHub.
2. Go to **Settings > Secrets and variables > Actions**.
3. Add the following Repository Secrets:
    - `POSTGRES_HOST`
    - `POSTGRES_USER`
    - `POSTGRES_PASSWORD`
    - `POSTGRES_DB`
    - `POSTGRES_PORT`
