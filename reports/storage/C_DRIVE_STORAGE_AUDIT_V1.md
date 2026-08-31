# C 盘存储审计 V1

生成时间：2026-08-31 14:34:54

## 磁盘可用空间

| 盘 | 可用 GB | 总 GB | 用途建议 |
|---|--------:|-----:|----------|
| C | 42.7 | 449.2 | 系统/配置 |
| D | 140.3 | 481.2 | 普通软件 |
| E | 155.7 | 500.0 | TreeCut 程序+运行数据 |
| G | 167.1 | 431.5 | AI 模型/缓存 |
| Z | 12172.5 | 14902.0 | 大型媒体 |

## C:\Users\admin 主要目录

| 目录 | 大小 GB | 分类 |
|------|-------:|------|
| Downloads | 21.33 | 用户文件-需审查 |
| AppData_Local_Temp | 17.48 | 临时-可清(审查) |
| .cache | 14.93 | 模型缓存-可迁G |
| Desktop | 7.50 | 用户文件-需审查 |
| .ollama | 5.56 | 模型-可迁G |
| dsh_models | 1.89 | 模型-可迁G |
| deepseek-harness | 1.07 | Harness 程序数据 |
| .dsh | 0.81 | Harness 数据 |
| github | 0.07 | 开发仓库(仅0.07GB) |
| harness_workspace | 0.02 | 工作区 |
| .treecut | 0.00 | TreeCut 用户数据(≈0) |
| .modelscope | 0.00 | 模型缓存(≈0) |

## Top 大文件（>50MB，取前 19）

| 大小 GB | 路径 |
| 2.88 | `C:\Users\admin\.cache\huggingface\hub\models--Systran--faster-whisper-large-v3\snapshots\edaa852ec7e145841d8ffdb056a99866b5f0a478\model.bin` |
| 2.12 | `C:\Users\admin\.cache\huggingface\hub\models--BAAI--bge-m3\snapshots\5617a9f61b028005a4858fdac845db406aefb181\pytorch_model.bin` |
| 2.12 | `C:\Users\admin\.cache\huggingface\hub\models--BAAI--bge-m3\snapshots\9a0624b896d81da7492a910ffa53731274b6cf3d\model.safetensors` |
| 1.59 | `C:\Users\admin\.cache\huggingface\hub\models--timm--vit_large_patch14_clip_224.openai\blobs\9ce2e8a8ebfff3793d7d375ad6d3c35cb9aebf3de7ace0fc7308accab7cd207e` |
| 1.59 | `C:\Users\admin\.cache\huggingface\hub\models--timm--vit_large_patch14_clip_224.openai\snapshots\18d0535469bb561bf468d76c1d73aa35156c922b\open_clip_model.safetensors` |
| 0.56 | `C:\Users\admin\.cache\huggingface\hub\models--openai--clip-vit-base-patch32\snapshots\3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268\pytorch_model.bin` |
| 0.56 | `C:\Users\admin\.cache\huggingface\hub\models--openai--clip-vit-base-patch32\snapshots\c237dc49a33fc61debc9276459120b7eac67e7ef\model.safetensors` |
| 0.45 | `C:\Users\admin\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots\536b0662742c02347bc0e980a01041f333bce120\model.bin` |
| 0.44 | `C:\Users\admin\.cache\huggingface\hub\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2\snapshots\e8f8c211226b894fcb81acc59f3b34ba3efd5f42\model.safetensors` |
| 0.43 | `C:\Users\admin\.cache\huggingface\hub\models--microsoft--Florence-2-base\snapshots\5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac\pytorch_model.bin` |
| 0.43 | `C:\Users\admin\.cache\huggingface\hub\models--microsoft--Florence-2-base\snapshots\5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac\model.safetensors` |
| 0.29 | `C:\Users\admin\.codex\plugins\.plugin-appserver\codex.exe` |
| 0.20 | `C:\Users\admin\.cache\huggingface\hub\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2\blobs\eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b.12f35e0b.incomplete` |
| 0.13 | `C:\Users\admin\.cache\huggingface\hub\models--openai--clip-vit-base-patch32\blobs\a63082132ba4f97a80bea76823f544493bffa8082296d62d71581a4feff1576f.1c0b0193.incomplete` |
| 0.09 | `C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe` |
| 0.09 | `C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages\artifact_tool_v2\bin\artifact_tool_rpc_daemon.exe` |
| 0.08 | `C:\Users\admin\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\1110a243fdf4706b3f48f1d95db1a4f5529b4d41\model.safetensors` |
| 0.08 | `C:\Users\admin\.codex\logs_2.sqlite` |
| 0.07 | `C:\Users\admin\.codex\plugins\.plugin-appserver\codex-code-mode-host.exe` |

## 结论

- TreeCut 本身在 C 盘仅占 ~0.07GB（仓库）；运行数据（DB/profile/快照）实际已在 E 盘
- C 盘压力主源：Downloads 21GB、Temp 17.5GB、.cache 15GB、Desktop 7.5GB、.ollama 5.6GB、dsh_models 1.9GB
- 可预测回收（不含用户文件审查项）：Temp 清理 + 模型缓存迁 G ≈ 26-33GB → C 回到 ~70-80GB
- 全部为规划；删除须 Phase B 验证 + 用户批准后执行