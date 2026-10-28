# 上游来源与许可

- [U-Boot Allwinner 官方文档](https://docs.u-boot.org/en/latest/board/allwinner/sunxi.html)：SPL/U-Boot 组合、TF-A、FEL 与 SPI 引导基础。
- [U-Boot 源码](https://source.denx.de/u-boot/u-boot)：上游引导器，依其许可证。
- [Armbian build](https://github.com/armbian/build) 与 [Armbian 软件源](https://apt.armbian.com/)：已验证 U-Boot 软件包来源。固定文件名与摘要见 `examples/validated-inputs.json`。
- [linux-sunxi sunxi-tools](https://github.com/linux-sunxi/sunxi-tools)：FEL 客户端与支持范围，应核对所使用版本的 H618 支持。
- [Orange Pi 官方 Wiki](https://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_3)：板型、接口和电源要求。页面不可用时请从厂商主页访问。
- [Ubuntu ARM Server](https://ubuntu.com/download/server/arm) 与 [Ubuntu 镜像验证说明](https://ubuntu.com/tutorials/how-to-verify-ubuntu)：获取并验证自己的 ISO。
- [Zadig 官方网站](https://zadig.akeo.ie/)：Windows 的指定 USB 设备驱动安装。
- [Linux initramfs 格式](https://docs.kernel.org/driver-api/early-userspace/buffer-format.html)：newc 与压缩成员。

本仓库没有复制上述工程的源代码树或分发第三方二进制。新写的辅助脚本和文档采用 MIT；下载的软件包、内核、固件及客户端仍遵循其上游许可，项目许可证不会为它们重新授权。
