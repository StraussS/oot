# Development Guide

## Environment

- Python 3.13
- Streamlit
- SQLite

## Local development

```bash
cd oot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.headless true --browser.gatherUsageStats false --server.address 0.0.0.0 --server.port 8502
```

## Main files

- `app.py`：主应用入口
- `requirements.txt`：Python 依赖
- `Dockerfile`：容器构建
- `docker-compose.yml`：容器编排
- `run.sh`：一键启动
- `update.sh`：一键更新

## Data files

- `oot.db`：SQLite 数据库
- `uploads/images/`：图片上传目录
- `uploads/invoices/`：发票上传目录

## Suggested workflow

1. 修改 `app.py`
2. 运行语法检查
3. 本地启动验证
4. 提交 git 变更

### Syntax check

```bash
python3 -m py_compile app.py
```

## Notes

- 系统 Python 可能是 externally managed，推荐使用 `.venv`
- Streamlit 首次运行时建议加：
  - `--server.headless true`
  - `--browser.gatherUsageStats false`
- 如果 8502 端口被占用，请先停止旧进程或容器
