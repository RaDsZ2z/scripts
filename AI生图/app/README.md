# Banana 工作台

这是 `laozhang_banana.py`、`ikun_banana.py` 和 `micu_gpt_image_2.py` 的本地浏览器界面。三个脚本仍可单独运行。

## 启动

双击 `start.bat`。程序会启动本地服务并自动打开浏览器。

如果首次启动提示缺少依赖，在当前目录运行：

```powershell
py -m pip install -r requirements.txt
```

如果电脑使用 `python` 命令，也可以将上述命令中的 `py` 替换为 `python`。

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

## API Key

API Key 统一保存在与脚本同目录的 `api_keys.env` 中。先复制 `api_keys.env.example`，再填写：

- `BANANA_API_KEY`
- `IKUN_BANANA_API_KEY`
- `MICU_API_KEY`

`api_keys.env` 已加入仓库根目录的 `.gitignore`，不会被 Git 跟踪。环境变量可覆盖文件中的同名配置；密钥不会发送到前端页面，也不应写入任何 Python 脚本。
