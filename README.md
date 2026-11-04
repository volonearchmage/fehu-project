# fehu-project

NTCIR-19 FEHU 研究项目，包含主体价值识别的数据、代码、实验记录、论文和组会材料。

- [项目与数据说明](ntcir19_fehu-master/README.md)
- [Task 2 研究判断、模型选择与实验设计](ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/Task2_研究判断与实验设计.md)
- [Task 2 组会 PPT](ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/Task2_主导研究方案.pptx)
- [研究文档和论文](ntcir19_fehu-master/docs/)
- [Task 1 实验](ntcir19_fehu-master/RH_test/)

Task 2 当前是待实现的实验方案：优先用 ModernBERT-base 比较普通联合训练与文章—子事件单向一致性训练。尚未产生该方案的训练成绩；已有 Task 1 结果和刘东阳的 Task 2 结果在文档中分别注明来源。

仓库保存本地项目中的代码、数据、预测及响应缓存、实验配置与日志、论文 PDF、PPT 和设计文档。`.env` 等凭据、虚拟环境、下载的依赖、运行缓存、模型权重及根目录 `tmp/` 中的临时构建和安装包不上传；这些文件保留在原电脑。GitHub 仓库因此是研究文件归档，不是整台电脑环境的逐字节备份。新的训练或推理仍需按对应实验脚本准备依赖及本机凭据。
