# 多 Agent 动态发包演示系统 - 无依赖一键启动包

## 启动方式

双击 `start_demo.bat` 即可启动。脚本只使用本目录内的运行时，不依赖系统已安装的 Java、Neo4j 或 Python。

内置运行时：

- `runtime/java21`：内置 Java 21
- `runtime/neo4j`：内置 Neo4j Community 2026.02.2
- `runtime/python312`：内置 Python 3.12
- `runtime/python_site`：内置 Flask、Neo4j driver 等 Python 依赖

首次启动会初始化 Neo4j 密码并导入声明图谱，可能需要 1-3 分钟。

> 兼容性说明：为避免 Neo4j 2026 在 Windows 中文父路径下读取配置/认证文件异常，`start_demo.bat` 会自动创建一个临时 `SUBST` 盘符别名（通常是 `M:`），让 Java、Neo4j、Python 通过 ASCII 路径运行。真实数据仍写回本包目录；`stop_demo.bat` 会清理该盘符别名。

## 访问地址

- Dashboard: <http://127.0.0.1:5000>
- Neo4j Browser: <http://127.0.0.1:7474>
  - user: `neo4j`
  - password: `Lzj.123456`

## 停止方式

双击 `stop_demo.bat`，或在命令行执行：

```bat
set NO_PAUSE=1
call stop_demo.bat
```

## 目录说明

- `app/`：Flask 后端、动态仿真器、前端页面、本地 ECharts
- `data/mabzt_comm_dataset/`：默认多 Agent 通信数据集
- `results/`：Neo4j 初始导入 Cypher、SQLite 运行库和动态实验输出
- `docs/`：方案文档和说明材料
- `logs/`：Neo4j、Flask、导入和认证检查日志
- `runtime/`：随包携带的 Java、Neo4j、Python 与 Python 依赖

## 可复现说明

源工程保留了打包脚本：`实验代码/build_portable_bundle.ps1`。如需从源工程重新构建本包，在 `最终实验` 目录下执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\实验代码\build_portable_bundle.ps1
```

打包脚本默认复制：

- Java: `E:\game\MCmod\bkm\java21`
- Neo4j: `E:\tools\WindowsDomainJail\neo4j-community-2026.02.2-windows\neo4j-community-2026.02.2`
- Python: `C:\Program Files\Python312`

便携包内部使用 ASCII 目录名（`app/data/results/docs/runtime/logs`），启动时再通过 `SUBST` 盘符别名规避 Windows CMD/Neo4j 对中文父路径的兼容性问题。
