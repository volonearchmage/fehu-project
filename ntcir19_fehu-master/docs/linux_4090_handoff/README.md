# Linux RTX 4090 与 Codex 交接

更新：2026-11-05。此处是迁移、环境维护和下一轮执行说明；实测结论以对应报告为准。

新机器首次迁移可执行 [提示词 1](01_sync_from_github.txt)。当前 Linux 4090 已恢复且 v2 全量 fit/tune 训练已完成，无需重复迁移、GPU 修复或旧学习检查。已核验研究提交为 `0da5687da453dc3f891468c19e8e80c4024d2618`；T/J/S tune Task2b micro-F1 为10.58%/10.92%/11.28%，P为11.37%。

当前使用 [方法审阅07](07_task2_method_review_20261105.md) 和 [ModernBERT自主研究指令08](08_run_modernbert_adaptive_research.txt)：先诊断正例学习，做匹配的WBCE/ASL对照，再按证据迭代。35%是内部工程目标，不等于官方TEST成绩。沿用[协议v2](05_task2_research_protocol_v2.md)的分组数据与计分契约；[指令06](06_run_task2_pilot_v2.txt)已执行，[旧指令04](04_finish_task2_after_gpu_ready.txt)不再作为准入门槛。

文档发布在 [GitHub main 的交接目录](https://github.com/volonearchmage/fehu-project/tree/main/ntcir19_fehu-master/docs/linux_4090_handoff)。Linux Codex 应按08开头步骤fetch并固定交接消息中的commit SHA，用git show读取05/07/08及根AGENTS/PROJECT_STATE，在已有研究分支继续。不要为了取得文档而pull、切换main或覆盖Linux的新代码与结果。

[6.17 下的 GPU 恢复流程](03_gpu_recovery_6_17.md) 保留作为维护记录和故障时参考；已恢复的机器无需再次照此重启或登记证书。

[提示词2](02_task2_local_experiment.txt)及训练前报告保留供追溯。Windows另有用户授权的[非思考Prompt与融合实验09](09_prompt_fusion_experiment_20261105.txt)，与Linux本地训练分开；旧DeepSeek full run停止标记仍保留，Linux不得调用付费API。研究分支 `task2-local-4090-20261104-2033` 尚未合并main，保留该分支及更晚本地工作。

## 权限与实际测试

先在 Linux 终端查看 `codex --version` 和 `codex --help`，以该机器版本为准。
启动设置影响新会话；提示词不能追溯性提升已启动会话的权限，也不能覆盖管理员策略。

同步需要改 Git 元数据。对这台由你控制、用于本项目的机器，可仅在本次同步会话使用：

```bash
# 先 cd 到现有仓库，或准备存放项目的父目录。
codex --sandbox danger-full-access --ask-for-approval never
```

这会关闭该会话的命令沙箱和审批，不是只对当前文件夹授权，也不会赋予 Linux root 权限。
不修改全局默认权限，不使用 `sudo codex`。提示词仍限制操作范围并禁止付费 API。

同步完成后退出，在最新仓库根目录启动实验会话：

```bash
codex --sandbox workspace-write --ask-for-approval never \
  -c sandbox_workspace_write.network_access=true
```

该设置允许工作区实验写入和依赖/模型下载；不弹审批，受限操作会失败。
当前官方文档说明 `.git`、`.codex` 等受保护路径在 workspace-write 下仍可能只读；`never` 不会自动允许 Git 提交。第二阶段先把代码和结果留在工作区，发布可另在明确授权的同步会话处理。

实际验收工作区临时写入、Git 远程读取、`nvidia-smi`、Python 和 CUDA 张量运算。看到 4090 名称不等于沙箱内 GPU 可用。缺驱动、下载访问或系统权限时记录具体阻塞，继续可做的离线工作，不自动改系统安全设置。

参数已核对本机 CLI help、[OpenAI 官方审批/安全文档](https://learn.chatgpt.com/docs/agent-approvals-security)和[配置说明](https://learn.chatgpt.com/docs/config-file/config-reference)。当前 Windows 会话没有连接 Linux 机器；Linux 仍需实测。4090 用于项目训练，不会自动把 Codex 自身变成本地免费模型。

## 内容与离线验收

上传冻结 prompt、实验代码、已保存请求/响应、508 条成功缓存、官方评价器、预测/gold/分数/误差表及交接提示词。`.env`、账户余额、权重、依赖环境和重复的中断 ZIP 不上传。

在 Git 根目录运行：

```bash
python3 ntcir19_fehu-master/research/task2_prompt_baseline_v1/verify_offline.py
```

它不读取凭据、不联网，只向 `ntcir19_fehu-master/output/task2_offline_verification/` 写新记录。
应复现 508 个事件、1,328 个候选和 Task-2a/2b Micro-F1 `0.3379069141781006` / `0.27903715821453606`。

历史 runner 存在 Windows 路径且停止保护未覆盖所有入口；不要运行历史 `run` 命令。`audit_results.py` 要求 1,526 条齐全，不用于这次验收。Git 行尾策略保留历史字节，不能修改 frozen hash 掩盖迁移差异。
