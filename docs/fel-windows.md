# Windows 串口与 FEL

## 接线与设备

板上独立三针 DEBUG TTL UART 不是 26 针排针上的其他 UART。使用 **3.3 V TTL 电平**：适配器 TX 接板 RX，RX 接板 TX，GND 接 GND，不接适配器 VCC。串口设置 115200、8N1、无流控。端口号以设备管理器为准，不写死在项目中。

CH340 只是串口桥。FEL 需要开发板本体 USB-C 使用可传输数据的线连接电脑，两者是不同设备。能看到串口并不代表已经连接 FEL。

若串口没有日志，先确认实际供电、独立三针位置和交叉接线。可把适配器从开发板完全断开后，单独短接其 TX/RX 做回环测试；不短接 VCC。旧 CH340 驱动若报设备错误，关闭占用串口的程序，拔插适配器后重新确认端口编号。

## 进入恢复模式

原板厂商 U-Boot 能从串口中断自动启动并执行 `efex`，随后出现 FEL。它不是所有 U-Boot 都共有的命令；以板上实际版本为准。若原 SPI 无法运行或被擦除，参考板厂恢复方法和上游文档，不要在不清楚硬件连接的情况下短接引脚。

Windows 需要为 **Allwinner FEL，USB ID `1F3A:EFE8`** 安装合适的 WinUSB 驱动。原部署使用 [Zadig](https://zadig.akeo.ie/)。核对设备及 VID/PID 后再安装，不能替换 CH340、键盘或其他 USB 设备的驱动。

安装后用支持本板 H618 的 FEL 客户端查询版本。查询失败时先解决数据线、接口和驱动问题；反复执行写内存命令不能修复物理连接。

## 临时 RAM 引导

使用 [sunxi-tools 上游](https://github.com/linux-sunxi/sunxi-tools) 中支持 H618 的版本和本项目固定摘要的 U-Boot 镜像。上游通常采用：

```text
sunxi-fel version
sunxi-fel -p uboot u-boot-sunxi-with-spl.bin
```

**这两条命令是上游接口示例，不表示所有 Windows 预编译版本均已验证。**原部署中旧客户端曾缺少 H618 的完整 SPL/64 位跳转支持，需要额外 RAM 交接处理；该临时调试实现和第三方 EXE 没有随项目分发。若看到 `No SPL support`、不能切到 AArch64、DRAM 初始化停住，先核对客户端支持，推荐按上游源码构建合适版本或改用 Linux 主机。

H618 的 SoC 标识及复位向量处理需要客户端实际支持；不能只因为工具名称相同就认定兼容。本项目不提供在未知客户端上自动写 SPI 的快捷命令。临时引导只应写 RAM，确认看到现代 U-Boot 串口日志后，再手工加载 FAT32 中的 boot.scr。

进入完整 USB 系统后，才使用 `zero3-spi plan/commit` 做持久 SPI 安装。日常启动不再依赖 Windows、FEL 或串口发送程序。
