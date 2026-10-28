# Orange Pi Zero 3 从 U 盘独立启动 Ubuntu

将一次实际完成的 **无 microSD、板载 SPI 引导、U 盘完整系统**部署整理为可检查的脚本和中文操作记录。启动链为：

```mermaid
flowchart LR
  A[H618 BootROM] --> B[板载 SPI 中的 SPL 与 U-Boot]
  B --> C[U 盘 FAT32 分区 boot.scr]
  C --> D[ARM64 Image 与 initrd 与板级 DTB]
  D --> E[U 盘 ext4 根文件系统]
```

完成 SPI 配置后，日常开机只需独立电源和 U 盘。电脑和 FEL 只用于初次准备或恢复。

## 已验证与适用范围

| 项目 | 实际记录 |
| --- | --- |
| 开发板 | Orange Pi Zero 3，H618，Linux 识别约 1.5 GiB RAM |
| 系统输入 | `ubuntu-26.10-live-server-arm64.iso` |
| 已验证内核 | `7.3.0-9-generic` |
| 引导器 | Armbian `linux-u-boot-orangepizero3-current` 26.8.3 |
| 存储 | 一只约 64 GB USB 存储器，约 8 GiB FAT32 启动分区，其余 ext4 |
| 独立冷启动 | 已在原部署中验证，2026-10-27 |
| 基础功能 | 串口、ext4 持久化、SSH 服务、4 个 CPU、交换文件 |

**仓库里的参数化脚本经过单元测试和原 ISO 文件准备验证；重新分区、重新刷 SPI 的通用化脚本未在另一块空白开发板上重新执行。**不要把这份记录理解为所有镜像、内存型号和 U 盘均已兼容。HDMI、Wi-Fi 驱动和后续内核升级不在已验证范围。

原 ISO 是部署时提供的输入；仓库中的摘要用于识别该输入，不能代替发行方的签名验证。

## 内容

- [完整安装流程](docs/installation.md)：先准备两分区，再从 Live 环境部署完整系统。
- [Windows 串口与 FEL](docs/fel-windows.md)：接线、WinUSB、进入 FEL 和临时 RAM 引导。
- [恢复与排错](docs/recovery.md)：备份、旧启动文件、FEL 和独立冷启动检查。
- [验证记录](docs/validation.md)：区分原部署的硬件验证与重构脚本验证。
- [脱敏说明](docs/privacy.md)：公开内容和本地敏感文件的边界。
- [上游与许可](docs/sources.md)：U-Boot、Armbian、sunxi-tools 和 Ubuntu 来源。

## 准备工具

电脑端 Python 3.11 或更新版本：

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

在电脑上的普通目录准备启动文件，不会格式化磁盘：

```sh
python -m zero3_usb_boot.prepare \
  --iso /path/to/ubuntu-26.10-live-server-arm64.iso \
  --iso-sha256 YOUR_TRUSTED_64_HEX_DIGEST \
  --output build/usb --copy-iso
```

PowerShell 请使用一行命令，或将上例的 `\` 换成 PowerShell 续行符。核对输出后，把 `build/usb/` **内部内容**复制到 U 盘的 FAT32 分区根目录。输出必须使用空目录，工具不会覆盖现有启动文件。

下载已验证的公开 U-Boot 包并核对两个 SHA256：

```sh
python tools/fetch_uboot.py --output build/firmware
```

若上游删除旧包，工具会失败；不会自动换成未验证的新版本。固件、ISO、原 SPI 备份和运行日志均不随仓库分发。

## 关键区别

通用 ARM64 安装 ISO 不能直接等同于这块板子的 USB 启动固件。此方案额外处理 U-Boot、板级 DTB、EFI zboot 内核展开、串口初始化和 USB 根文件系统依赖。

ISO Live 安装环境与完整系统是两个阶段。仅进入 Live 界面，并不代表已经得到重启后保留数据的完整系统。SPI 中也只放引导器，不放 Ubuntu 系统。

## 测试

```sh
python -m unittest discover -s tests -v
python tools/check_public_tree.py
```

测试不会格式化磁盘或写入 SPI。`zero3-spi plan` 只备份和生成本地计划；只有显式运行 `commit` 并匹配原始备份摘要才会调用 `flashcp`。首次操作请先完整阅读安装和恢复文档。

项目代码使用 MIT 许可证。外部固件和工具沿用各自上游许可。
