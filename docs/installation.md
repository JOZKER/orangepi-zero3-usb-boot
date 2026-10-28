# 完整安装流程

这是一份供新安装参考的手工流程，不会在你打开仓库时自动执行。对已有系统，请先备份；分区和格式化会删除目标 U 盘上的数据。仓库不提供对任意现有 FAT32 分区原地缩容的脚本，原部署中的一次性扇区改写操作没有公开。

## 1 准备条件

- 已验证型号为 Orange Pi Zero 3 H618，约 1.5 GiB RAM。
- 一只容量足够的 U 盘，建议至少 32 GB；原部署约 64 GB。
- 稳定的独立 USB-C 电源，按开发板官方要求选取；初次 FEL 操作另外需要数据线。
- 3.3 V TTL 串口适配器，接独立三针 DEBUG 口，参数 115200、8N1、无流控。
- 可运行 Python 的电脑；分区和完整系统部署步骤使用 Linux。Windows 可以完成 ISO 文件准备、串口和 FEL，ext4 和 chroot 阶段需要 ARM64 Live 环境。
- 部署时需要可访问 Ubuntu Ports / Python 包源的网络，或自行准备对应 ARM64 系统的离线包。本项目不提供网络认证绕过。

首次操作前先读 [FEL 文档](fel-windows.md) 和 [恢复文档](recovery.md)。所有设备路径都要按现场识别，不能把示例设备名直接当作自己的 U 盘。

## 2 先给空 U 盘分区

使用 Linux 的磁盘工具核对型号、容量和序列号，建立 **MBR/msdos 分区表**：

| 分区 | 建议布局 | 文件系统 | 用途 |
| --- | --- | --- | --- |
| 第 1 分区 | 从 1 MiB 开始，到约 8 GiB | FAT32 | ISO、boot.scr、Image、initrd、DTB |
| 第 2 分区 | 其余空间 | ext4 | 完整 Ubuntu 根文件系统 |

原部署启动分区从扇区 32 开始，是保留旧 U 盘布局的结果，不是必须复刻的要求。这里建议空盘从 1 MiB 对齐。脚本使用文件系统 UUID，不依赖某只 U 盘的 UUID、序列号或准确容量。

格式化后，在电脑上用 README 的 `zero3_usb_boot.prepare` 准备 Live 文件。程序会校验 ISO、展开 ARM64 EFI zboot、从同一内核包取 DTB、按框架决定串口修复，再生成带 CRC 的 boot.scr。

将输出目录内部的文件复制到 FAT32 根目录，包括 ISO。不要把目录本身再嵌套一层。保留 `boot.cmd`、`boot.scr` 的副本，分别命名为 `boot-live.cmd`、`boot-live.scr`，后面可用于进入安装环境。

此阶段不要将 U-Boot 固件直接 dd 到 U 盘来代替板载 SPI 配置；该方案的持久启动链是板载 SPI 到 USB。

## 3 从 RAM U-Boot 进入 Live

参照 FEL 文档，把适配本板的 SPL/U-Boot 临时加载到 RAM。看到现代 U-Boot 提示符后：

```text
usb start
load usb 0:1 0x4f000000 /boot.scr
source 0x4f000000
```

观察串口是否进入 Ubuntu Live 环境。此时系统仍是安装环境，尚未完成持久安装。此阶段不需要先写 SPI，便于失败时重试。

## 4 识别并挂载目标根分区

在开发板的 Live 串口终端进入 root shell。先检查：

```sh
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS,MODEL
findmnt
cat /cdrom/casper/install-sources.yaml
```

手工确认目标分区后设置 `ROOT_PART` 和 `BOOT_PART`。以下两个占位路径必须替换，不能指向 Live 的 squashfs 或当前根设备：

```sh
ROOT_PART=/dev/disk/by-id/usb-YOUR_DEVICE-part2
BOOT_PART=/dev/disk/by-id/usb-YOUR_DEVICE-part1
mkdir -p /target /mnt/zero3-boot
mount "$ROOT_PART" /target
mount "$BOOT_PART" /mnt/zero3-boot
```

第二分区应是刚准备的空 ext4。不要在有资料的分区上继续复制系统。

## 5 部署 ISO 中的完整 Server 根文件系统

已验证输入的 `install-sources.yaml` 中，默认 `ubuntu-server` 类型为 `fsimage-layered`：

```text
ubuntu-server-minimal.squashfs
ubuntu-server-minimal.ubuntu-server.squashfs
```

必须按层叠加，不能只复制任意一个 squashfs：

```sh
mkdir -p /mnt/zero3-base /mnt/zero3-layer /mnt/zero3-source
mount -t squashfs -o loop,ro /cdrom/casper/ubuntu-server-minimal.squashfs /mnt/zero3-base
mount -t squashfs -o loop,ro /cdrom/casper/ubuntu-server-minimal.ubuntu-server.squashfs /mnt/zero3-layer
mount -t overlay -o ro,lowerdir=/mnt/zero3-layer:/mnt/zero3-base overlay /mnt/zero3-source
cp -a -x /mnt/zero3-source/. /target/
sync
```

其他 ISO 的层名和布局可能不同，应以其安装源描述为准；不要无条件照用这些文件名。

## 6 配置目标系统

先获取本机 UUID，在目标 `/etc/fstab` 写入根分区和启动分区挂载项。以下命令只把现场值写进你的 U 盘，不应把生成文件提交到公开仓库：

```sh
ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")
BOOT_UUID=$(blkid -s UUID -o value "$BOOT_PART")
printf 'UUID=%s / ext4 defaults,noatime,errors=remount-ro 0 1\nUUID=%s /boot/firmware vfat defaults,umask=0077 0 2\n' "$ROOT_UUID" "$BOOT_UUID" > /target/etc/fstab
printf '{"root_uuid":"%s"}\n' "$ROOT_UUID" > /target/etc/zero3-boot.json
mkdir -p /target/boot/firmware
mount --bind /mnt/zero3-boot /target/boot/firmware
mount --rbind /dev /target/dev
mount --make-rslave /target/dev
mount -t proc proc /target/proc
mount --rbind /sys /target/sys
mount --make-rslave /target/sys
```

按自己的需要设置主机名、时区、账户、DHCP 和软件源。Ubuntu ARM64 应使用 Ubuntu Ports 源。若离线从 ISO 安装软件，应按 ISO 的发行代号配置本地源；不能在长期系统中遗留只供安装阶段使用的 cdrom 源。

下列操作在 `chroot /target /bin/bash` 中执行；账户名 `boarduser` 是公开示例，不是预设账户，也没有默认密码：

```sh
useradd -m -s /bin/bash -G sudo,adm,dialout boarduser
passwd boarduser
passwd -l root
systemctl enable ssh.service serial-getty@ttyS0.service
systemctl set-default multi-user.target
```

如 `sudo`、OpenSSH 尚未安装，先从受信的源安装。生成每台机器独有的 SSH 主机密钥，不要复制另一台开发板的密钥。网络配置可使用匹配以太网接口名称 `e*` 的 netplan DHCP 规则；核对实际接口，不要绑定原部署的 MAC。

## 7 安装本项目及内核发布钩子

在目标系统里安装本项目及 Python 依赖，建议使用专用 venv，例如 `/usr/local/lib/zero3-usb-boot/.venv`。软件源和网络需先可用，或使用自行准备的离线依赖。保留该 venv，不要在建立钩子后移动它。

在目标 `/etc/dracut.conf.d/50-zero3-usb.conf` 添加：

```text
add_drivers+=" i2c_mv64xxx axp20x_i2c axp20x_regulator phy_sun4i_usb ehci_platform ohci_platform usb_storage sd_mod ext4 "
```

仅在匹配已验证环境时使用此 dracut 配置。对 initramfs-tools 应使用相应的模块配置文件，而不是把 dracut 配置原样照搬。

在 `/etc/initramfs/post-update.d/zz-zero3` 建立可执行钩子：

```sh
#!/bin/sh
set -eu
exec /usr/local/lib/zero3-usb-boot/.venv/bin/zero3-publish "$1" "$2"
```

确认 `/etc/flash-kernel/machine` 的策略不会让通用 `flash-kernel` 覆盖本方案；原部署设为 `none`。其他引导管理器的钩子需按系统实际情况检查。

在目标 chroot 中，使用真实安装的内核版本：

```sh
KVER=7.3.0-9-generic
update-initramfs -u -k "$KVER"
/usr/local/lib/zero3-usb-boot/.venv/bin/zero3-publish "$KVER" --dry-run
/usr/local/lib/zero3-usb-boot/.venv/bin/zero3-publish "$KVER"
```

工具把每一代 Image、initrd、DTB 放到独立目录，确认文件写完后才替换 boot.scr。不会修改发行版原始内核和 initrd。对于 dracut，保留其原生 `/init`；只有识别到已知 initramfs-tools 布局才加串口覆盖层。

## 8 先验证 USB 完整系统，再写 SPI

退出 chroot，正确卸载 `/target` 的子挂载并同步。在 RAM U-Boot 中重新加载启动分区当前 boot.scr。进入完整系统后检查根分区确为第二分区的 ext4，创建测试文件，再重启确认其保留。

此时从 U 盘完整系统运行 SPI 工具：

```sh
sudo zero3-spi plan --device /dev/mtd0 \
  --image /path/to/u-boot-sunxi-with-spl.bin \
  --sha256 YOUR_VERIFIED_UBOOT_IMAGE_DIGEST \
  --output /root/zero3-spi-backup
```

把完整 `spi-original.bin` 和 `plan.json` 复制到另一台电脑，校验 SHA256。确认后才执行：

```sh
sudo zero3-spi commit --plan /root/zero3-spi-backup/plan.json \
  --confirm-original-sha256 YOUR_SAVED_ORIGINAL_FLASH_DIGEST
```

工具再次核对板型、16 MiB/4 KiB SPI、固件摘要和原始内容，调用 `flashcp`，再回读比对。它不会为其他容量或名称的 MTD 强行继续。

## 9 独立冷启动

正常关机，断开电脑的 USB-C 数据连接，等待电源灯完全熄灭，再接独立电源。U 盘保留。电脑串口可以只监听，不执行任何 FEL 加载命令。

检查能否自动进入完整系统、测试文件是否保留。运行 `zero3-verify` 获取不含网络身份的当前状态。该命令本身不能证明冷启动过程；必须结合断电操作和串口观察。使用稳定供电，关机用 `sudo poweroff`。
