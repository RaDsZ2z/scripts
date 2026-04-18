# 协议模拟器使用说明（服务器端）

## 这是什么

一个 Python 命令行工具，用于模拟游戏客户端连接服务器、发送/接收协议。
不需要启动 Unity 客户端，不需要前端环境。

---

## 环境准备

### 1. 安装 Python 3.8+

下载地址：https://www.python.org/downloads/

安装时勾选 "Add Python to PATH"。

### 2. 安装依赖

打开终端（cmd 或 PowerShell），运行：

```bash
pip install protobuf colorama grpcio-tools
```

### 3. 拿到工具包

把 `proto_simulator/` 文件夹放到任意目录，比如 `D:\tools\proto_simulator\`。

然后在该目录的**上一级**打开终端（上面的例子就是 `D:\tools\` 目录下）。

---

## 快速开始

### 第一步：确认能用

```bash
cd D:\tools
python -m proto_simulator --help
```

看到帮助信息说明环境正常。

### 第二步：连接服务器

```bash
python -m proto_simulator --ip 192.168.1.100 --port 8080 --uin 10001 --server-id 1 --sign 你拿到的签名
```

参数说明：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--ip` | 游戏服务器 IP | `192.168.1.100` |
| `--port` | 游戏服务器端口 | `8080` |
| `--uin` | 测试账号的玩家 ID | `10001` |
| `--server-id` | 服务器 ID | `1` |
| `--sign` | 登录签名（Base64 编码） | `YWJjZGVm...` |

> **sign 怎么来？**
>
> 从登录接口返回的 `sign` 字段获取。
> 你作为服务端开发，可以直接从数据库或登录流程中生成一个。
> 也可以在内网开一个免签名测试入口，此时 sign 传空字符串 `""` 即可。

### 第三步：发协议

连接成功后进入交互模式，光标前会出现 `proto>` 提示符：

```
proto> send GetUserInfo
```

服务器返回的消息会自动显示在屏幕上。

---

## 交互模式命令

### 查看协议字段 — desc（最重要）

**不知道协议要传什么参数？先 desc 一下：**

```
proto> desc FarmlandStart
```

输出示例：

```
协议: FarmlandStart  (ID: 15003)

CSFarmlandStart (客户端 → 服务器):
  farmland_id: int32  (field 1)
  ingredient_id: int32  (field 2)
  is_all: bool  (field 3)

SCFarmlandStart (服务器 → 客户端):
  farmlands: repeated message
    farmland_id: int32  (field 1)
    props: repeated message
      prop_id: int32  (field 1)
      prop_num: int64  (field 2)
  ingredient_id: int32  (field 2)
  is_all: bool  (field 3)

发送示例:
  send FarmlandStart {}
  send FarmlandStart {"farmland_id": 0, "ingredient_id": 0, "is_all": false}
```

会显示：
- **CS 字段**：你需要传什么参数
- **SC 字段**：服务器会返回什么（嵌套消息会展开）
- **发送示例**：直接复制，改上实际值就能用

### 发送协议 — send

```
proto> send <协议名> [JSON参数]
```

示例：

```bash
# 无参数请求
proto> send GetUserInfo

# 带参数请求（先 desc 查看需要什么字段）
proto> send FarmlandStart {"farmland_id": 1, "ingredient_id": 1001, "is_all": false}

# bytes 字段传 base64 字符串
proto> send SendDelayMessage {"delay_data": "dGVzdA==", "message_id": 10001}

# 数组字段传 JSON 数组
proto> send FriendSendGift {"uins": [10001, 10002], "is_all": false}

# 嵌套消息传 JSON 对象
proto> send PropOpenBox {"box_id": 1, "count": 1}
```

**JSON 参数规则：**
- 普通字段直接写值：`"farmland_id": 1`
- 布尔值用 `true` / `false`
- bytes 字段传 base64 字符串
- 数组字段传 JSON 数组：`"uins": [1, 2, 3]`
- 嵌套消息传 JSON 对象
- 协议名可以不带 CS 前缀，`send FarmlandStart` 和 `send CSFarmlandStart` 效果一样

### 搜索协议 — help

```bash
# 列出所有命令
proto> help

# 按关键词搜索协议
proto> help farm
proto> help friend
proto> help order
```

### 等待服务器消息 — wait

```bash
# 等待特定协议（默认 30 秒超时）
proto> wait SCNotifyUpdateProps

# 指定超时
proto> wait SCNotifyFarmland 10
```

### 其他命令

```bash
proto> status              # 查看连接状态
proto> heartbeat now       # 手动发一次心跳
proto> heartbeat off       # 关闭自动心跳
proto> quit                # 退出（会自动发送 CSLogout）
```

---

## 典型工作流

```
1. 连接服务器
   python -m proto_simulator --ip ... --port ... --uin ... --sign ...

2. 先拉取角色信息，确认连接正常
   proto> send GetUserInfo

3. 不确定某个协议要传什么？先 desc
   proto> desc FarmlandStart

4. 复制发送示例，填上实际参数
   proto> send FarmlandStart {"farmland_id": 1, "ingredient_id": 1001, "is_all": false}

5. 观察服务器返回，确认接口行为

6. 退出
   proto> quit
```

---

## 批量测试

### 写测试脚本

创建一个 JSON 文件，例如 `test_basic.json`：

```json
{
    "steps": [
        {
            "name": "获取角色信息",
            "send": "GetUserInfo",
            "wait_for": "SCGetUserInfo",
            "timeout": 5
        },
        {
            "name": "获取农田数据",
            "send": "NotifyFarmlandFullInfo",
            "wait_for": "SCNotifyFarmlandFullInfo",
            "timeout": 5
        },
        {
            "name": "开始种植",
            "send": "FarmlandStart",
            "params": {
                "farmland_id": 1,
                "ingredient_id": 1001,
                "is_all": false
            },
            "wait_for": "SCFarmlandStart",
            "timeout": 5
        },
        {
            "name": "收获",
            "send": "FarmlandHarvest",
            "params": {"farmland_id": 1},
            "wait_for": "SCFarmlandHarvest",
            "timeout": 5,
            "abort_on_fail": true
        }
    ]
}
```

**字段说明：**

| 字段 | 必须 | 说明 |
|------|------|------|
| `name` | 否 | 步骤名称（显示用） |
| `send` | 是 | 要发送的协议枚举名（不带 CS 前缀） |
| `params` | 否 | 协议参数，JSON 对象 |
| `wait_for` | 否 | 期望收到的响应协议名（带 SC 前缀） |
| `timeout` | 否 | 等待超时秒数，默认 10 |
| `abort_on_fail` | 否 | 失败后是否终止，默认 false |

### 运行批量测试

```bash
python -m proto_simulator --ip ... --port ... --uin ... --sign ... --batch test_basic.json
```

运行结束后会显示：`测试完成: 4 通过, 0 失败`

---

## 协议名称速查

协议名使用枚举名（不带 CS/SC 前缀），send 时会自动匹配 CS 前缀的类。

| 系统 | 协议 ID 范围 | 示例协议 |
|------|------------|---------|
| 框架 | 10000-10999 | Login, Logout, HeartBeat |
| 玩家 | 11000-11999 | GetUserInfo, Rename, UpdateSetting |
| 道具 | 11100-11199 | PropOpenBox, PropExchange, DebugAddProp |
| 称号/头像/头像框 | 11400-11499 | EquipTitle, EquipAvatar |
| 社交/好友 | 14000-14099 | GetFriendList, ApplyAddFriend |
| 黑名单 | 14050-14099 | GetBlacklist, AddBlacklist |
| 农田 | 15000-15999 | FarmlandStart, FarmlandHarvest |
| 食材 | 16000-16999 | IngredientLevelUp, StartBreed |
| 菜肴台 | 17000-17999 | MakeDish, DishTableUnlock |
| 订单 | 21000-21999 | CompletedGeneralResidentOrder |
| 邮件 | 30001-30099 | ReadMail, DeleteMail |
| 任务 | 30301-30399 | TaskReceiveReward |
| 商店 | 30900-30999 | StoreBuy |
| 充值 | 49000-49999 | BuyCard, ReceiveCardDailyReward |

在交互模式中用 `help 关键词` 或 `desc 协议名` 随时查询。

---

## 常见问题

### 连接超时

- 检查 IP 和端口是否正确
- 检查服务器是否已启动
- 检查防火墙是否放行了端口

### 登录失败（NotifyFail）

- sign 可能已过期，重新获取一个
- 确认 uin 和 server-id 对应正确

### 找不到协议

- 输入 `help 关键词` 搜索
- 协议名使用枚举名，不带 CS 前缀。例如 `FarmlandStart` 而不是 `CSFarmlandStart`
- 也可以直接用 CS 前缀：`send CSFarmlandStart`

### 不知道协议要传什么参数

- 用 `desc 协议名` 查看字段结构
- 底部会给出 `发送示例`，复制后改数字即可

### 心跳断开

- 默认 30 秒自动发心跳，连接应该能保持
- 如果服务器踢人，检查是否被其他逻辑踢出

### 需要更新的协议

如果前后端新增了协议，需要前端同事更新以下文件后重新给你工具包：
1. `config.py` 中的 `MESSAGE_DEFINE` 字典
2. `_generated/` 目录（用 `--compile` 重新编译）

---

## 给前端同事的反馈

如果发现协议行为不符合预期，把终端里的输出发给前端同事即可。
输出包含：
- 发送的消息名和 ID
- 发送的字段内容
- 服务器返回的消息内容
- 错误信息（如有）
