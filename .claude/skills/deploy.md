# Deploy / Start Dashboard

Start or restart the Streamlit dashboard server.

## Commands

### Start server
```bash
C:/Users/Master/Anaconda3/envs/dashboard/Scripts/streamlit.exe run src/dashboard/Home.py
```

### Check if running
```bash
netstat -ano | findstr :8501
```

### Install new dependency
```bash
C:/Users/Master/Anaconda3/envs/dashboard/Scripts/pip.exe install <package>
```
Then add to `requirements.txt`.

### Run a quick Python test
```bash
C:/Users/Master/Anaconda3/envs/dashboard/python.exe -c "<code>"
```

## Environment

- Conda env: `dashboard` at `C:/Users/Master/Anaconda3/envs/dashboard/`
- Working dir: `D:/ai/Dashboard`
- Default port: 8501 → http://localhost:8501
- Path `.pth` file: `C:/Users/Master/Anaconda3/envs/dashboard/Lib/site-packages/dashboard.pth` (enables `import src.*`)

## Steps

1. If the user says the server is crashing, read the error traceback and fix the root cause
2. Never use `--no-verify` or skip import checks
3. After fixing a bug, remind the user to hard-refresh the browser (Ctrl+Shift+R) to clear Streamlit cache
