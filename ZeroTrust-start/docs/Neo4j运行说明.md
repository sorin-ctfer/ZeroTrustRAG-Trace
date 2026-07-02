# Neo4j 运行说明

本机 Neo4j 路径来自用户提供信息：

```text
E:\tools\WindowsDomainJail\neo4j-community-2026.02.2-windows\neo4j-community-2026.02.2\bin
```

`neo4jhelp.txt` 内容：

```bat
set JAVA_HOME=E:\game\MCmod\bkm\java21
neo4j.bat console
```

本实验已经据此生成三个脚本：

- `实验代码/start_neo4j.ps1`：设置 `JAVA_HOME` 后启动 Neo4j。
- `实验代码/import_neo4j.ps1`：把 `实验结果/neo4j_import.cypher` 导入 Neo4j。
- `实验代码/run_demo.ps1 -StartNeo4j`：启动 Neo4j、生成数据、运行实验并启动 Flask 前端。

常用命令：

```powershell
cd E:\daily\3-吴永贤\备课\最终版\最终实验\实验代码
.\run_demo.ps1 -StartNeo4j
```

如果 Neo4j 已经启动，仅导入图谱：

```powershell
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="你的密码"
.\import_neo4j.ps1
```

也可以在前端点击“导出/同步 Neo4j”。无论是否连接成功，系统都会生成可手工导入的 `实验结果/neo4j_import.cypher`。

## 当前状态

- 已将本地 Neo4j 用户 
eo4j 的密码重置为用户指定密码。
- 已成功导入 实验结果/neo4j_import.cypher。
- 当前图谱节点：Agent 54、Claim 1200、Evidence 480、Tool 1200、Claim_Group 480、Action 240。

