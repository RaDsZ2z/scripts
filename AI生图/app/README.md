# Banana 工作台

这是 `laozhang_banana.py` 和 `ikun_banana.py` 的本地浏览器界面。原脚本仍可单独运行。

## 启动

双击 `start.bat`。程序会启动本地服务并自动打开浏览器。

如果首次启动提示缺少依赖，在当前目录运行：

```powershell
python -m pip install -r requirements.txt
```

推荐使用最新版 Chrome 或 Edge。页面仅通过 `127.0.0.1` 在本机访问。

## 工作区

1. 点击页面右上角的“选择文件夹”。
2. 选择本次使用的 workspace，并允许浏览器读写。
3. 参考图片必须位于该 workspace 内。
4. 将参考图拖入对应的任务，填写提示词后提交批次。

结果保存在：

```text
workspace/output/月_日_时_分_秒/
```

批次结束后，`tasks_next.json` 会写入 workspace 根目录。点击“导出任务”会在同一位置写入 `tasks_export.json`。

## 导入格式

JSON 与原脚本兼容。`image_path` 可以是字符串或数组，导出时始终使用数组。相对路径以当前 workspace 为基准。

Excel 使用 `.xlsx` 格式，第一行包含 `prompt` 和可选的 `image_path`。一行对应一条任务；多张参考图路径使用英文或中文分号分隔。

## API Key

工具优先读取环境变量：

- `BANANA_API_KEY`
- `IKUN_BANANA_API_KEY`

未设置环境变量时，会沿用两个原脚本中的 `API_KEY`。密钥不会发送到前端页面。
