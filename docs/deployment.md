# 部署说明

## 环境要求

- Python 3.10+
- Node.js 20.19+ 或 22.12+（已在 Node.js 22.22 验证）
- npm 10+

## 本地启动

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell 使用：

```powershell
.\.venv\Scripts\Activate.ps1
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- Swagger：`http://127.0.0.1:8000/docs`

## 前端 API 地址

开发模式默认通过 Vite 将 `/api` 代理到 `127.0.0.1:8000`。独立部署时可设置：

```bash
VITE_API_BASE=https://your-api.example.com/api npm run build
```

## Docker Compose

```bash
docker compose up
```

首次启动会安装依赖，耗时取决于网络。生产环境建议构建固定镜像，而不是每次启动在线安装。

## 验证

```bash
cd backend
pytest

cd ../frontend
npm install
npm run build
```

## 运行时数据

知识库和风险报告写入：

- `backend/app/data/knowledge_store.json`
- `backend/app/data/reports/`

这些文件已加入 `.gitignore`。内置案例位于 `backend/app/data/web_cases/`，会提交到仓库。

## 故障排查

### 上传接口提示 multipart 缺失

```bash
pip install python-multipart
```

### 前端接口请求失败

确认后端端口为 `8000`，并检查 `VITE_API_BASE` 或 Vite proxy 配置。

### 图谱较密集

可拖拽节点、滚轮缩放并悬停查看节点与边。高风险节点使用红色显示。

### 端口被占用

修改 Uvicorn `--port` 后，同时更新 Vite proxy 或 `VITE_API_BASE`。

## 安全与实验声明

部署实例只应使用本地模拟数据。当前实验结果不是公开基准成绩，不应作为生产环境检测能力承诺。
