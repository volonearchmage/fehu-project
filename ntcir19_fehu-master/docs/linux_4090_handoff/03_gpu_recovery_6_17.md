# Linux RTX 4090 在 6.17 内核下的恢复流程

更新日期：2026-11-04，日本时间。适用对象：机器所有者、现场协助人员、系统管理员和协助执行的 AI。

**2026-11-05 状态更新：用户回传 GPU 阻塞已解除，真实模型与优化器更新、更新后最长输入及 checkpoint 重载验收通过。下文记录此前故障及恢复流程，已恢复的机器不应重复执行。下一步见 [实验执行指令](04_finish_task2_after_gpu_ready.txt)。Linux 原始恢复报告位于 `output/linux_handoff/gpu_recovered_20261105-003426/GPU_RECOVERY.md`。**

**目标：保留现有 Ubuntu 和 6.17.0-40 内核，恢复 RTX 4090 的驱动与 CUDA 运算，再进行 Task 2 训练验收。** 当前优先处理现有 NVIDIA 模块的证书信任问题。7.0 内核修复另行安排。

本文是待执行的维护说明。编写、收到或阅读本文，不代表已执行维护，也不自动授权 AI 重启或修改系统。当前没有经过验证的免重启恢复方案。没有现场人员或能控制开机界面的远程控制台时，停在只读核对阶段。

## 1 给现场人员的速查流程

现场人员可以不熟悉机器学习，但需要能够看见屏幕、操作键盘，并与管理员保持电话或其他独立联系。提前把本节保存到手机或另一台电脑，重启时 AnyDesk 会断开。

1. **先不要重启。** 管理员先核对证书、6.17 启动文件和启动菜单，把第 4 节的现场信息表填写完整。
2. 现场人员到位，确认能操作开机菜单、知道 Linux 登录方式；机器所有者已经同意本次维护窗口。
3. 管理员登记已核实的 MOK 公共证书。操作人员在终端设置临时注册密码，并通过合适的私下方式让负责开机操作的人知晓。不要把密码写入本文、聊天或日志。
4. 保存工作后正常重启。看到 MOK 管理界面时，核对证书，按第 6 节完成注册。此过程可能需要再次重启，现场人员继续守候。
5. 到 GRUB 启动菜单后，选择已核实的 **6.17.0-40-generic 普通启动项**。不要选择 7.0；正常验收不选择 recovery mode。
6. 进入 Linux，确认能登录、桌面和 AnyDesk 恢复，再让管理员执行驱动及 CUDA 验收。
7. 遇到与说明不一致的界面，保留画面并联系管理员。不要尝试清除密钥、恢复 BIOS 默认设置或临时修复 7.0。

**本流程允许出现的结果有三种：恢复成功；返回 6.17 但 GPU 仍失败；系统未能正常返回、由现场管理员继续接管。不能只看到“证书注册成功”就宣布 GPU 已修好。**

## 2 电脑现状和项目进度

### 2.1 系统现状

下表中的系统事实来自 Linux Codex 的诊断转述和用户反馈；本文件编写端在 Windows，没有直接登录 Linux 或读取其原始系统日志。执行前应以 Linux 上的原报告和现场只读结果为准。

| 项目 | 已有记录 | 对本次维护的意义 |
| --- | --- | --- |
| GPU | NVIDIA GeForce RTX 4090，PCI 层可见 | 硬件被枚举不代表驱动和 CUDA 可用 |
| 当前内核 | 6.17.0-40-generic | 本次恢复和重启后验收均以它为目标 |
| NVIDIA 驱动 | 590.48.01；6.17 对应模块已构建并签名 | 不能把“模块已安装”当作“内核已加载” |
| Secure Boot | 当前开启；日志记录不可信签名密钥导致模块拒载 | 主路径是核对并注册现有匹配证书 |
| 7.0.0-28 内核 | NVIDIA DKMS 编译失败，包配置未完成，initramfs 缺失；用户反馈启动报错 | 暂不选择该内核，也不把修复它作为恢复 4090 的前提 |
| 远程连接 | 目前依赖 AnyDesk，无法靠它可靠控制 MOK 或 GRUB 界面 | 重启前必须安排现场或开机前控制台接管 |
| Codex 权限 | Linux 报告为 danger-full-access / never，执行和联网已验证 | Codex 权限不会改变内核对驱动签名的信任 |

用户所说的“旧系统”和“新系统”，在现有证据中主要对应同一 Ubuntu 的不同内核启动项。不要因此重装操作系统。

历史记录曾显示同一 6.17 内核和 590 驱动在 Secure Boot 关闭时加载成功，且有 RTX 4090 的 DeBERTa 训练记录；也记录了开启后拒载。当前拒载足以解释眼下的 GPU 故障，但不能仅凭当前状态判断是谁、通过什么操作改变了设置，也不能断言证书从未注册过。

### 2.2 项目和 Python 环境

已直接核对 GitHub 研究分支的[训练前报告](https://github.com/volonearchmage/fehu-project/blob/9d162c6dd8e971cd58e1e240891892de129dc62b/ntcir19_fehu-master/research/task2_scope_local_v1/review/PRETRAINING_REPORT.md)。代码、训练数据和完整预训练权重已有准备，真实 ModernBERT 已在 CPU 上完成两个完整短 bag 的前向、反向和单次参数更新。该结果证明软件链路可运行，尚不证明 GPU、长输入显存或模型效果。

| 项目 | 当前记录 |
| --- | --- |
| Linux 工作副本 | `/home/szf-4090/projects/fehu-project-main-2da2ea5` |
| 嵌套项目目录 | 上述 Git 根下面的 `ntcir19_fehu-master/` |
| 研究分支 | `task2-local-4090-20261104-2033` |
| 已核实提交 | `9d162c6dd8e971cd58e1e240891892de129dc62b`；研究工作未合并 main |
| 模型 | `answerdotai/ModernBERT-base`，revision `8949b909ec900327062f0ebf497f51aef5e6f0c8` |
| CPU 专用环境 | 项目 `.venv/bin/python`，PyTorch `2.6.0+cpu` |
| GPU 验收所用环境 | `/home/szf-4090/miniconda3/envs/fehu/bin/python`，原 FEHU，PyTorch `2.6.0+cu124` |
| 正式训练 | 尚未开展；CPU 验证不能替代 J/S 正式实验 |

**修好驱动后，CPU 版 `.venv` 仍然是 CPU 版。第 7 节用绝对路径调用原 FEHU Python，避免激活错环境。** 不需要为了本次维护重建 Python 环境或重新下载权重。完整权重保存在这台 Linux 的本地缓存，未随 Git 提交；换机器时仍需按锁文件取得或迁移并核验哈希。

## 3 为什么涉及重启

MOK 是 Machine Owner Key，允许 Ubuntu 信任用户授权的模块签名证书。`mokutil --import` 在正在运行的 Linux 中创建待注册请求；启动阶段的 MokManager 由操作人员确认注册，新启动过程才能按新的信任状态加载模块。登记请求不会让当前内核立即接受该证书。[Ubuntu Secure Boot 说明](https://documentation.ubuntu.com/security/security-features/platform-protections/secure-boot/)

因此，普通重启但没有完成正确证书的注册，可能仍然遇到同一拒载问题；注册成功后也仍需验证驱动和 CUDA。限制加载不可信模块是内核的签名策略，普通 `sudo` 或 Codex 的 full-access 不会自动绕过它。[Linux 内核模块签名说明](https://docs.kernel.org/admin-guide/module-signing.html)

这里的重启是让同一台电脑重新经过固件、启动管理器和 Linux 启动过程。它不会主动把内核升级为 7.0；但若默认启动项指向 7.0，自动倒计时可能选中它，所以需要现场人员明确选择 6.17。重启期间 AnyDesk 断开属于预期现象，恢复时间不能预先保证。

本流程保留 Secure Boot，不把关闭验证、生成新密钥、重新签名全部模块或更换驱动作为默认操作。

## 4 重启前核对

### 4.1 执行范围和分工

下文所有命令都是 **Linux Bash 命令，必须在目标 Linux 主机执行**，不能粘贴到 Windows PowerShell。按小节逐块执行并检查输出，不要把整篇文档当脚本运行。预期可能失败的诊断命令应保留错误信息，不能因退出码非零而假定后续步骤已完成。

| 阶段 | 执行人 | 执行条件 |
| --- | --- | --- |
| 查看报告、证书和启动文件 | AI 或管理员 | 可以只读进行；涉及受限文件时由管理员提供访问 |
| 登记证书和启动重启 | 管理员，可由 AI 协助 | 维护已获授权，现场人员或开机前控制台就绪，证书与启动路径已核实 |
| MOK 和 GRUB 界面 | 现场人员或控制台操作人 | 能看见实际屏幕并输入，掌握临时密码和目标启动项 |
| 恢复验收 | 管理员或 AI | Linux 已返回；只运行本次授权的验收，不自动启动正式训练 |

当前用户要求编写流程，没有要求此刻执行系统变更。未来维护开始时，一次确认本次范围和现场条件即可；不要对范围内的每条常规命令重复询问。条件不满足时说明具体缺项，保留现状。

### 4.2 先读本机已有报告

以 Git 根目录为基准，阅读：

- `ntcir19_fehu-master/output/linux_handoff/environment_report.md`
- `ntcir19_fehu-master/output/linux_handoff/gpu_environment_20261104-205148/ADMIN_RECOVERY.md`
- `ntcir19_fehu-master/output/linux_handoff/readonly_modules_20261104-212022/KERNEL7_READONLY.md`
- `ntcir19_fehu-master/research/task2_scope_local_v1/review/PRETRAINING_REPORT.md`

前面三个路径来自 Linux 的诊断记录，未在已核对的研究提交中获得其原文。若本机路径已变化，先查找对应文件；不要把找不到报告当作可以猜测证书路径的理由。

确认工作副本和内核：

```bash
cd /home/szf-4090/projects/fehu-project-main-2da2ea5 || exit 1
pwd -P
git status --short
git branch --show-current
git rev-parse HEAD
uname -r
cat /proc/sys/kernel/random/boot_id
cat /etc/os-release
mokutil --sb-state
test -d /sys/firmware/efi
```

`test` 成功通常没有输出。若不是预期的 Linux 主机、当前内核已变化，或系统现状与报告不同，先重新判断适用性，不继续套用后面的变更步骤。保留未提交工作，不执行 reset、clean 或强制切换分支。

### 4.3 核对 6.17 启动文件和实际菜单

```bash
FEHU_KVER='6.17.0-40-generic'
ls -l -- "/boot/vmlinuz-$FEHU_KVER" "/boot/initrd.img-$FEHU_KVER"
lsinitramfs "/boot/initrd.img-$FEHU_KVER" > /dev/null
sudo awk '/^[[:space:]]*(menuentry|submenu)[[:space:]]/ {print}' /boot/grub/grub.cfg
```

文件存在和 initramfs 可读只是重启前核对，不能保证启动成功。命令缺失或权限不足时记录原因，由管理员判断，不顺手安装软件或运行包修复。

再只读核对 `/etc/default/grub`、存在的 `/etc/default/grub.d/*.cfg`，以及 `sudo grub-editenv /boot/grub/grubenv list` 的结果。记录默认项、菜单是否隐藏、超时和已有 saved/next entry。若既有配置启用了保存所选启动项，手动选择也可能影响以后默认项；不要承诺手选完全没有持久影响。

常见目标菜单为 `Advanced options for Ubuntu` 下的 `Ubuntu, with Linux 6.17.0-40-generic`，**必须用本机实际菜单名称替换**。本次不编辑 GRUB，不运行 `update-grub`、`grub-set-default` 或 `grub-reboot`。[GNU GRUB 配置说明](https://www.gnu.org/software/grub/manual/grub/html_node/Simple-configuration.html)

本次需要经过启动管理器完成 MOK 操作。另做以下只读核对，排除可能绕过完整启动过程的特殊重启安排；具体行为以本机 systemd 版本为准：

```bash
systemctl --version
if [ -r /sys/kernel/kexec_loaded ]; then
  cat /sys/kernel/kexec_loaded
else
  printf '%s\n' 'kexec 状态接口不可读，请由管理员核对本机配置。'
fi
if [ -e /run/nextroot ]; then
  printf '%s\n' '/run/nextroot 存在，请暂停并由管理员核对。'
else
  printf '%s\n' '/run/nextroot 不存在。'
fi
```

可读的 `kexec_loaded` 应为 `0`，`/run/nextroot` 应不存在。显示已预载、存在特殊根目录或无法判断时，先由管理员检查本机行为，不卸载 kexec、不删除目录、不借用未经本机版本验证的重启参数。

### 4.4 核对模块和现有公共证书

先检查实际安装在目标内核下的模块：

```bash
modinfo -k "$FEHU_KVER" -F filename nvidia
modinfo -k "$FEHU_KVER" -F version nvidia
modinfo -k "$FEHU_KVER" -F vermagic nvidia
modinfo -k "$FEHU_KVER" -F signer nvidia
modinfo -k "$FEHU_KVER" -F sig_key nvidia
```

应与目标内核和报告中的 `590.48.01` 相符。管理员也应核对 `nvidia_modeset`、`nvidia_drm`、`nvidia_uvm` 等实际使用的配套模块是否属于同一构建和签名方案。模块缺失、版本不同或签名关系不明时，不进入证书导入步骤。

把下面变量替换为本机报告和管理员核实的 **DER 公共证书绝对路径**。`/var/lib/shim-signed/mok/MOK.der` 是常见路径示例，尚不能在本文中当作本机实测路径。不要读取、复制或上传 `MOK.priv` 等私钥。

```bash
FEHU_CERT='/ABSOLUTE/PATH/TO/VERIFIED/MOK.der'
test -f "$FEHU_CERT"
openssl x509 -inform DER -in "$FEHU_CERT" -noout \
  -subject -issuer -serial -dates -fingerprint -sha256
openssl x509 -inform DER -in "$FEHU_CERT" -noout -fingerprint -sha1
mokutil --test-key "$FEHU_CERT"
mokutil --list-new
mokutil --list-delete
```

检查证书来源、有效期、签名者和序列号等标识，并对照原诊断中的模块签名关系。**不要把 `modinfo` 的 `sig_key` 和证书 SHA256 指纹直接比较。** kmod 的 PKCS#7 解析实现中，该标识来自签名者证书序列号；标识相符也不等于已完成密码学验签。指纹用于辨认同一证书，两个界面必须按同一种算法比较。[kmod 官方实现](https://raw.githubusercontent.com/kmod-project/kmod/master/libkmod/libkmod-signature-openssl.c)

`--test-key` 用于查询注册状态；`--list-new`、`--list-delete` 用于核对待处理请求。若证书已注册但仍拒载，或已有不明的注册/删除请求，应先查清，不重复导入或批准整批未知请求。[mokutil 手册](https://manpages.ubuntu.com/manpages/noble/man1/mokutil.1.html)

### 4.5 填好现场信息表

| 必须记录的内容 | 现场填写 |
| --- | --- |
| 维护时间和时区 |  |
| 机器确认信息和现场/控制台联系人 |  |
| 管理员与现场人员的独立联系渠道 |  |
| 当前内核和目标内核 |  |
| GRUB 实际入口和 6.17 完整菜单名称 |  |
| 已验证的菜单唤出方式 |  |
| 证书绝对路径、subject、serial、有效期 |  |
| 证书 SHA256 指纹；界面需要时附 SHA1 指纹 |  |
| 原有待注册/待删除请求是否已查明 |  |
| 未保存工作已保存，其他使用者的任务已协调 |  |
| 本次维护授权和现场接管条件已确认 |  |

临时 MOK 密码和 Linux 登录密码均不填入表格。开机界面无法控制、目标菜单不可确认、现场人员未到位，任一项出现就不要导入证书或重启。

## 5 登记证书并正常重启

本节会修改待注册状态并中断当前远程连接，只能在第 4 节条件满足后的维护窗口执行。

### 5.1 管理员登记已核实的证书

继续使用同一个 Linux 终端中的 `FEHU_CERT`；如果换了终端，要先重新设置并核对该变量。

```bash
test -f "$FEHU_CERT" &&
  sudo mokutil --import "$FEHU_CERT" &&
  mokutil --list-new
```

操作人员按终端提示输入临时注册密码。它用于随后 MokManager 的确认，和 `sudo` 登录密码用途不同。不要用带明文密码的命令、脚本或聊天代替交互输入。完成后确认待注册列表包含且只涉及管理员已认可的证书请求。任何一步失败，或待请求与预期不符，停在本节，不进入 5.2；不得把原有待请求列表当作本次导入成功。此时只是登记成功，GPU 尚未恢复。

如果本次维护取消，且管理员确认当前待导入请求全部属于本次，可使用 `sudo mokutil --revoke-import` 撤销。它撤销整个当前待导入请求，并非只撤销某一个证书，也不删除已经注册的证书。不要自动执行它。[mokutil 手册](https://manpages.ubuntu.com/manpages/noble/man1/mokutil.1.html)

### 5.2 保存工作并发起重启

确认现场人员已经看着屏幕、键盘可用、临时密码可用，且能够操作 6.17 启动项。保存当前编辑内容和必要的会话记录，协调机器上其他任务。不要依赖重启后恢复同一个终端或内存中的会话。

执行一次正常重启：

```bash
sudo systemctl reboot
```

此命令在前述启动路径检查完成后使用。不使用强制参数，不把关机或拔电当作正常重启；不添加未经本机版本验证的环境变量来声称保证某种启动行为。[systemctl 手册](https://manpages.ubuntu.com/manpages/noble/man1/systemctl.1.html)

AnyDesk 或终端断开后，由现场人员接管第 6 节。远程 AI 不要因断线重复发送重启，也不要声称已经观察到启动完成。

## 6 现场完成注册并选择 6.17

### 6.1 MokManager 界面

MOK 管理界面本身可能有蓝色或其他背景，不应仅凭颜色认定为此前的 7.0 启动错误。读取实际标题和选项。

典型操作顺序如下，界面文字可能随版本变化：

1. 启动出现进入 MOK 管理的提示时，按屏幕要求进入，不错过倒计时。
2. 选择 `Enroll MOK`。
3. 用 `View key` 等查看功能核对证书。对照第 4 节记录；若界面显示 SHA1，就比较记录中的 SHA1。
4. 确认是预期证书后，返回并选择 `Continue`，按提示选择 `Yes`。
5. 输入刚才 `mokutil --import` 时设置的临时密码。
6. 按提示选择 `Reboot`，继续留在机器旁。

证书不一致、出现未知待处理证书、密码遗忘或菜单含义不明时，先停止注册操作并记录画面。不要选择删除全部密钥、关闭验证或恢复固件默认值；在管理员指导下尝试继续进入已知 6.17 系统。[Ubuntu 注册说明](https://documentation.ubuntu.com/security/security-features/platform-protections/secure-boot/)、[Red Hat 官方界面流程](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/interactively_installing_rhel_from_installation_media/booting-a-beta-system-with-uefi-secure-boot_rhel-installer)

### 6.2 GRUB 启动菜单

进入本机实际的高级选项，选择第 4 节记录的 `6.17.0-40-generic` 普通启动项。留意 MOK 注册后再次启动的那一轮，同样不能放任默认项进入 7.0。

若菜单隐藏，优先使用这台机器此前成功选择旧内核的方法。GRUB 在适用的倒计时阶段可能接受 Esc、F4 或 Shift，但不保证所有固件与零秒超时配置都能靠这些按键显示菜单；若未事先验证唤出方法，不应开始无人恢复保障的重启。[GNU GRUB 配置说明](https://www.gnu.org/software/grub/manual/grub/html_node/Simple-configuration.html)

进入 Linux 后先登录，确认桌面和远程连接可用，再交回远程管理员或 AI。**本次能手动进入 6.17，不等于以后自动重启也会选择 6.17。** 默认启动策略应记录在结果中，若需要修改，作为另一个明确范围的维护事项处理。

## 7 恢复后的验收

### 7.1 系统和驱动

在恢复后的 Linux 终端执行；重启后旧 shell 变量已经丢失，需要重新填写已核实的证书路径。

```bash
uname -r
mokutil --sb-state
FEHU_CERT='/ABSOLUTE/PATH/TO/VERIFIED/MOK.der'
mokutil --test-key "$FEHU_CERT"
nvidia-smi
cat /proc/driver/nvidia/version
```

验收目标是：运行内核为 `6.17.0-40-generic`；证书注册状态与预期一致；驱动实际加载；`nvidia-smi` 显示 RTX 4090 且无驱动通信错误。仅 `mokutil` 成功或仅 PCI 可见都不够。驱动版本若与维护前记录不符，先解释差异再继续。

### 7.2 原 FEHU 环境的真实 CUDA 运算

下面是小型运算检查，不进行模型训练，不访问网络：

```bash
FEHU_PY='/home/szf-4090/miniconda3/envs/fehu/bin/python'
PYTHONDONTWRITEBYTECODE=1 "$FEHU_PY" - <<'PY'
import torch

print("torch:", torch.__version__)
print("compiled CUDA:", torch.version.cuda)
assert torch.version.cuda is not None, "Wrong environment: CPU-only PyTorch"
assert torch.cuda.is_available(), "CUDA is unavailable"
name = torch.cuda.get_device_name(0)
print("GPU:", name)
assert "4090" in name, "Unexpected GPU"
x = torch.arange(12, dtype=torch.float32, device="cuda").reshape(3, 4)
y = x @ x.T
torch.cuda.synchronize()
reference = torch.arange(12, dtype=torch.float32).reshape(3, 4)
torch.testing.assert_close(y.cpu(), reference @ reference.T)
bf16 = torch.cuda.is_bf16_supported()
print("BF16 supported:", bf16)
assert bf16, "BF16 is required by the planned experiment"
print("CUDA_CHECK_PASS")
PY
```

若失败，保存完整报错，不通过改成 CPU 运算获得“通过”。驱动正常但 Python 失败时，应检查实际解释器、CUDA 包和运行环境；不要立即重装系统驱动。

### 7.3 Task 2 训练可用性

系统维护可以在 7.1 和 7.2 成功并保存记录后结束。若本次还授权了模型 GPU 验收，再继续本节；正式 J/S 全量训练另按项目实验安排执行。

在研究分支的 `PRETRAINING_REPORT.md` 中已有真实的 `gpu_preflight.py` 调用命令，可使用核实后的本地缓存路径执行。不要在仍停留于旧 main、缺少研究代码的副本中盲目运行，也不要覆盖已有输出。

现有 [GPU 预检代码](https://github.com/volonearchmage/fehu-project/blob/9d162c6dd8e971cd58e1e240891892de129dc62b/ntcir19_fehu-master/research/task2_scope_local_v1/gpu_preflight.py)覆盖 J/S 前向和反向，**没有执行优化器更新，记录为 `optimizer_updates=0`**。因此，正式训练前还需由项目 AI 用现有训练组件补齐一次有明确边界的实际更新验收，不能把不存在的验收命令写成已实现入口。

最少覆盖内容如下：

- 用同一固定 revision 的完整 ModernBERT、实际 BF16 配置与 J/S 损失，包含代表性短输入和最长 fit bag。
- 最长 bag 为 article `33-2677-7-t`、actor `33-2677-7-t-0`，已有冻结方案为 8192/2097 tokens 两窗；不能为通过验收而静默截断、漏事件或改标签。
- 完成真实前向、反向、AdamW 参数更新，确认损失、梯度和参数有限且参数实际变化。优化器状态分配后，再处理最长 bag，记录显存峰值和耗时；必要时验证后续更新峰值。
- 单独核对 checkpoint 写入和重新加载。验收更新后的权重与正式实验隔离，正式 J/S 从原始预训练权重和相同初始化重新开始。

CPU 两个短样本的秒级耗时不能用于预测 8K GPU 训练时间。GPU 预检记录绑定当前启动、代码和输入；之后若重启或修改相关内容，需要检查记录是否仍有效。不要人为改 JSON 绕过检查。

## 8 异常时怎么处理

| 现象 | 立即处理 | 之后如何判断 |
| --- | --- | --- |
| 重启前证书、菜单或现场条件未确认 | 不导入、不重启 | 补齐第 4 节，不扩大维修范围 |
| 登记后决定取消本次维护 | 保持运行，管理员判断是否撤销本次待导入请求 | 不自动清空别人的请求，不删除已注册 MOK |
| 没有出现 MOK 菜单 | 尝试按已知路径进入 6.17 | 核对 `--test-key` 和 `--list-new`，不无限重启 |
| MOK 密码错误或证书不符 | 停止批准，记录界面，联系管理员 | 不猜密码、不批准未知证书、不关闭验证 |
| 误入 7.0 或出现原来的启动报错 | 现场保留画面，由管理员指导回到启动菜单，选择 6.17 | 若能正常重启，优先正常方式；系统完全失去响应时由现场管理员评估恢复，不让远程 AI 盲目发硬关机指令 |
| 6.17 未返回桌面或 AnyDesk | 现场继续接管，记录屏幕，若可登录终端则收集当前启动日志 | 不自动卸载模块、不重启显示服务、不恢复固件默认值 |
| 6.17 能进入，但 GPU 仍失败 | 保持系统状态，保存当前启动的驱动错误 | 重新定位本次具体错误，不自动转入驱动升级、7.0 修复或全局包修复 |
| GPU 小运算通过，真实模型 OOM | 记录触发输入、显存和配置 | 先核对其他进程的显存占用和运行配置；不直接判定系统驱动修复失败，也不静默删数据 |

失败时可只读收集：

```bash
uname -r
mokutil --sb-state
mokutil --list-new
mokutil --list-delete
nvidia-smi
journalctl -k -b --no-pager
```

日志权限不足时由管理员读取。聚焦当前启动的 NVIDIA、签名、锁定策略和模块错误，记录完整相关上下文；不因单个历史告警就判定当前仍失败。

本次不执行 `apt upgrade`、`apt autoremove`、广泛的驱动重装、`dpkg --configure -a` 或内核清理。机器已有 7.0 未完成包配置，宽泛操作可能触发额外变更。本次也不卸载正在使用的显示模块，不关闭 Secure Boot，不清除 MOK。

## 9 记录结果并交回项目

在项目 `output/linux_handoff/` 下新建按实际时间命名的维护目录，保留原报告，不覆盖历史结果。记录中明确使用日本时间或写出实际时区。

```text
维护日期与时区：
维护执行人及现场/控制台方式：
维护前/后的 boot ID、uname -r：
Git 分支、HEAD、未提交文件状态：
证书路径、指纹、注册前后状态：
实际执行的变更命令及结果：
MOK 和 GRUB 实际操作、异常画面：
nvidia-smi 和驱动版本：
FEHU Python 路径、torch/CUDA 版本、CUDA 运算结果：
桌面与 AnyDesk 是否恢复：
默认启动项是否仍可能进入 7.0：
系统 GPU 恢复：通过 / 未通过
真实模型训练验收：未执行 / 通过 / 未通过
正式训练：未启动 / 另行记录
未解决事项及下一步：
```

boot ID 可由 `cat /proc/sys/kernel/random/boot_id` 读取。保持 Task 1、旧推理结果、1997 个历史证据文件和 `USER_STOP.json` 不变。维护记录不包含密码、私钥、`.env` 或 API key。

验收完成后，再安排本地 J/S 实验，P 复用 J 结果。DeepSeek 付费实验保持停止；修复 GPU 不构成恢复付费 API 的授权。

## 10 给接手 AI 的指令

```text
先完整阅读本流程、根 AGENTS.md，以及 Linux 本机已有环境诊断和 ADMIN_RECOVERY.md。
确认当前机器、研究分支、6.17 内核、证书与 GRUB 实际入口；区分已验证事实与待核对项。

本流程的目标是恢复现有 6.17.0-40 下的 RTX 4090，不推进 7.0 修复。
只收到文档时先做只读核对，不把阅读文档视为执行系统变更的授权。
若本轮已明确授权维护，且现场人员或开机前控制台已就绪，按流程执行范围内操作，
不逐条重复询问。系统 sudo/MOK 密码由授权人员交互输入，不向聊天索取密码。

遇到证书不符、未知待处理请求、启动条件缺失或系统状态变化，停止依赖该条件的操作，
说明实际缺项；不要通过扩展权限、关闭 Secure Boot、重装驱动或修复 7.0 绕过去。
重启断线期间由现场人员接管；重新连接后以实际 boot ID、内核和 CUDA 运算判断结果。

使用原 FEHU CUDA Python 验收，不使用 CPU 专用 .venv。
系统恢复与真实模型训练验收分开记录；现有 gpu_preflight 没有 optimizer.step，
不要把其通过写成完整训练显存已验证。正式训练和付费 API 不自动启动。
保存新维护记录，保留旧环境、历史结果和 USER_STOP.json，不覆盖或伪造原报告。
```
