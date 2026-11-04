# fehu-project

NTCIR-19 FEHU 研究项目，包含主体价值识别的数据、代码、实验记录、论文和组会材料。

**最新状态（2026-11-04）：Task 2 付费 prompt 实验已停止，已完成 508/1,526 个子事件的官方子集评分。Task-2a Micro-F1 为 33.79%，Task-2b 为 27.90%；这是非随机完成子集，不是完整 DEV 或 TEST。**

- [Linux + RTX 4090 迁移与 Codex 权限说明](ntcir19_fehu-master/docs/linux_4090_handoff/README.md)
- [提示词 1：从 GitHub 同步并离线验收](ntcir19_fehu-master/docs/linux_4090_handoff/01_sync_from_github.txt)
- [提示词 2：本地 Task 2 J/S/P 实验](ntcir19_fehu-master/docs/linux_4090_handoff/02_task2_local_experiment.txt)
- [本次 prompt 官方评分和分析](ntcir19_fehu-master/research/task2_prompt_baseline_v1/subset_evaluation_completed/RESULTS_zh.md)
- [项目当前状态](PROJECT_STATE.md)

- [项目与数据说明](ntcir19_fehu-master/README.md)
- [Task 2 研究判断、模型选择与实验设计](ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/Task2_研究判断与实验设计.md)
- [Task 2 组会 PPT](ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/Task2_主导研究方案.pptx)
- [研究文档和论文](ntcir19_fehu-master/docs/)
- [Task 1 实验](ntcir19_fehu-master/RH_test/)

Task 2 本地监督训练仍是待实现的方案：优先用 ModernBERT-base 比较普通联合训练 J、单向一致性训练 S 及 J 的概率乘积后处理 P。尚未产生该方案的训练成绩；API prompt 子集结果、Task 1 结果和刘东阳的 Task 2 报告分开记录。迁移到 Linux 不代表恢复付费 API。

仓库保存本地项目中的代码、数据、预测及响应缓存、实验配置与日志、论文 PDF、PPT 和设计文档。`.env` 等凭据、虚拟环境、下载的依赖、运行缓存、模型权重及根目录 `tmp/` 中的临时构建和安装包不上传；这些文件保留在原电脑。GitHub 仓库因此是研究文件归档，不是整台电脑环境的逐字节备份。新的训练或推理仍需按对应实验脚本准备依赖及本机凭据。
