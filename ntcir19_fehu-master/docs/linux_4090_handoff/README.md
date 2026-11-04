# Linux RTX 4090 与 Codex 交接

更新：2026-11-04。此处是迁移和下一轮执行说明，不是 Linux 实测报告。

先执行 [提示词 1](01_sync_from_github.txt)，完成同步、离线复评和环境检查，再执行 [提示词 2](02_task2_local_experiment.txt)。第二阶段按已有方案进行 ModernBERT J/S/P 本地训练，保留 DeepSeek prompt 子集作为参考，不恢复付费实验。

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
