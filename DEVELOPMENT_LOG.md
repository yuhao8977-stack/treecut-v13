# DEVELOPMENT_LOG.md — TreeCut 开发日志（总控自主推进）

> 总控指令 V1 要求：每通过一个 Gate 更新本文件 + PROJECT_STATE.md + BACKLOG.md

## 2026-08-19（总控自主执行）

| Gate | 状态 | commit | 关键结果 |
|---|---|---|---|
| P0 审计+Git基线 | ✅ DONE | 4f5f9bd（v13仓库基线） | 双架构盘点、Z盘~4.6万视频~2.9TB |
| P1 扫描+资产库+任务队列 | ✅ DONE | 4f5245d | assets 表、ffprobe、断点续跑、v12迁移 |
| P1.1 生命周期+幂等+增量 | ✅ DONE | 1d385e8 | 10阶段×9状态机、should_process、依赖图、移动/改名复用、分层哈希 |
| P2 场景+关键帧+ASR+OCR | ✅ DONE | 5361312 | 真实成片 20段/60帧/ASR中文23段/OCR 142条(47硬字幕)；幂等重跑0重复 |
| P3 成片/原片+重复+TC标签 | ✅ DONE | 7b53d47 | 真实成片均 FINISHED；人工标签 human_override；精确重复分组 |
| P4 混合检索 | ✅ DONE | df5ff29 | BGE-M3 dim1024 FAISS ntotal43；查询"岛台 收纳 插座"语义相关 0.60/0.54 |
| P5 CT01/CT02 模板引擎 | 进行中 | - | 模板定义+槽位+候选推荐 |
| P6 人工选镜+粗剪 | 待办 | - | - |
| P7 CT03-CT12 | 待办 | - | - |
| P8 全系统QA | 待办 | - | - |
| P9 渐进式素材分析 | 待办 | - | - |

## 环境要点（P2-P4 实测）
- v13 runtime 缺依赖需装：scenedetect/rapidocr/faiss-cpu/sentence-transformers（清华源）
- faster-whisper：device="cpu"（无 cublas64_12）；HF_HUB_OFFLINE=1 + 用户级缓存回退
- FAISS/OpenCV 中文路径：临时 ASCII 目录 + imencode/fromfile 方案
- Z 盘（\\X1\素材01）：2.67TB 已用/11.89TB 可用，稳定可访问
