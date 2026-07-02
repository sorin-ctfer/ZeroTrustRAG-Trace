# Runtime 目录说明

本仓库不包含体积较大的运行时二进制文件，只保留占位目录。

请在运行项目前自行准备并放入以下目录：

- `runtime/java21/`：JDK 21 运行环境
- `runtime/neo4j/`：Neo4j 运行环境
- `runtime/python312/`：Python 3.12 运行环境

放置完成后，目录结构示例：

```text
runtime/
  java21/
  neo4j/
  python312/
```

`.gitkeep` 仅用于让 Git 保留空目录，放入实际运行时文件后无需提交这些二进制内容。
