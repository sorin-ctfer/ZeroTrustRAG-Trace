# Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest
```

Swagger: <http://127.0.0.1:8000/docs>

后端只处理本地模拟数据，不调用在线大模型或真实安全服务。

