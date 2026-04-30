# Win7 USB 打印客户端

这个客户端只使用 Windows 系统默认打印机。打印机接电源和 USB，电脑安装好驱动并设为默认打印机即可，不需要网线，也不需要配置打印机网络。

## 本地调试 GP-L80180

开发调试时，打印机接在当前 Windows 电脑上即可。先把佳博 GP-L80180 设为 Windows 默认打印机，然后在 `config.json` 里使用：

```json
{
  "font_name": "SimSun",
  "font_size": 9,
  "margin_mm": 3,
  "line_spacing": 1.28,
  "orientation": "feed",
  "rotation_degrees": 270
}
```

`orientation: "feed"` 会把文字旋转到和走纸长边平行。如果打出来上下颠倒或方向反了，把 `rotation_degrees` 改成 `90` 后重启客户端再试。

## 服务器配置

在上海服务器启动后端前设置同一个令牌：

```bat
set PRINT_CLIENT_TOKEN=your-secret-token
```

Linux 服务里可以把 `PRINT_CLIENT_TOKEN=your-secret-token` 写入 systemd 环境或启动脚本。

## Win7 打包

建议在 Win7 电脑上安装 Python 3.8 32 位或 64 位，然后在本目录运行：

```bat
build_win7_exe.bat
```

生成文件在 `dist\fy_print_client.exe`。把 `config.example.json` 复制为 `config.json`，并填写上海服务器地址和令牌。

## 开机自启

把 `fy_print_client.exe`、`config.json`、`install_autostart.bat` 放在同一个固定目录，然后双击：

```bat
install_autostart.bat
```

之后电脑开机登录当前 Windows 用户时，客户端会后台启动并轮询服务器。
