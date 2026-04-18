# -*- coding: utf-8 -*-
"""
Garden Protocol Simulator — 入口点

用法:
  python -m proto_simulator --compile                         # 编译 proto 文件
  python -m proto_simulator --ip IP --port PORT [OPTIONS]     # 直连模式
  python -m proto_simulator --server-url URL [OPTIONS]        # HTTP 登录模式

Options:
  --compile                仅编译 proto 文件
  --ip IP                  服务器 IP (直连模式)
  --port PORT              服务器端口 (直连模式)
  --uin UIN                玩家 UIN
  --server-id ID           服务器/组 ID (默认 1)
  --sign SIGN              Base64 编码的登录签名
  --batch FILE             批量模式，运行 JSON 测试脚本
  --server-url URL         服务器基础 URL (HTTP 登录模式)
  --platform PLATFORM      平台标识 (默认 intra)
  --channel CHANNEL        渠道标识 (默认 intra)
  --account ACCOUNT        账号
  --token TOKEN            登录令牌
  --no-heartbeat           禁用自动心跳
  --no-color               禁用彩色输出
  --verbose                详细输出模式
"""

import argparse
import json
import os
import sys
import urllib.request

# 确保从 Scripts/ 目录可以找到模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proto_simulator.config import MESSAGE_DEFINE
from proto_simulator.proto_compiler import compile_protos, ensure_generated
from proto_simulator.message_registry import MessageRegistry
from proto_simulator.connection import GameConnection
from proto_simulator.login import login_direct, login_http
from proto_simulator.heartbeat import HeartbeatManager
from proto_simulator.interactive import InteractiveMode
from proto_simulator.batch import BatchRunner
from proto_simulator import display


def parse_args():
    parser = argparse.ArgumentParser(
        description="Garden Protocol Simulator - 游戏协议模拟器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 编译
    parser.add_argument("--compile", action="store_true", help="仅编译 proto 文件，不连接")
    parser.add_argument("--force-compile", action="store_true", help="强制重新编译 proto 文件")

    # 连接参数
    parser.add_argument("--ip", help="服务器 IP (直连模式)")
    parser.add_argument("--port", type=int, help="服务器端口")
    parser.add_argument("--uin", type=int, help="玩家 UIN")
    parser.add_argument("--server-id", type=int, default=1, help="服务器/组 ID (默认 1)")
    parser.add_argument("--sign", help="Base64 编码的登录签名")

    # HTTP 登录
    parser.add_argument("--server-url", help="服务器基础 URL (HTTP 登录)")
    parser.add_argument("--platform", default="intra", help="平台标识 (默认 intra)")
    parser.add_argument("--channel", default="intra", help="渠道标识 (默认 intra)")
    parser.add_argument("--account", help="账号")
    parser.add_argument("--token", help="登录令牌")

    # 运行模式
    parser.add_argument("--batch", help="批量模式，运行 JSON 测试脚本")
    parser.add_argument("--no-heartbeat", action="store_true", help="禁用自动心跳")
    parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    return parser.parse_args()


# ── 默认连接参数（不传参数时使用这些值） ──────────────
DEFAULT_IP = "ip"
DEFAULT_PORT = 111
DEFAULT_UIN = 222
DEFAULT_SERVER_ID = 333
DEFAULT_LOGIN_URL = (
    "https://xxxx"
    "?platform=xxx&channel=xxx&account=xxx"
    "&server=xxx&login_token=xxx"
    "&extend=xxx"
)


def fetch_login_sign(url):
    """从登录 URL 获取 sign 凭证。"""
    display.info(f"正在获取登录凭证 ...")
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read().decode())
    except Exception as e:
        display.error(f"获取登录凭证失败: {e}")
        return None

    if not data.get("status"):
        display.error(f"登录凭证请求失败: {data.get('message')}")
        return None

    sign = data["data"].get("sign", "")
    display.success(f"  Sign: {sign[:40]}...")
    return sign


def main():
    args = parse_args()

    # 用默认值补充未传入的参数
    if not args.ip:
        args.ip = DEFAULT_IP
    if not args.port:
        args.port = DEFAULT_PORT
    if not args.uin:
        args.uin = DEFAULT_UIN
    if args.server_id == 1 and not args.sign:  # 只在没传 sign 时覆盖 server_id
        args.server_id = DEFAULT_SERVER_ID
    if not args.sign:
        args.sign = fetch_login_sign(DEFAULT_LOGIN_URL)
        if not args.sign:
            display.error("无法获取登录凭证，退出")
            sys.exit(1)

    # 彩色输出
    if args.no_color:
        display.enable_color(False)

    display.separator()
    display.info("Garden Protocol Simulator v1.0")
    display.separator()

    # ── 仅编译模式 ──
    if args.compile or args.force_compile:
        ok = compile_protos(force=args.force_compile)
        sys.exit(0 if ok else 1)

    # ── 确保 proto 已编译 ──
    if not ensure_generated():
        display.error("Proto 编译失败，请检查错误信息")
        display.info("提示: 可单独运行 --compile 查看详细错误")
        sys.exit(1)

    # ── 初始化注册表 ──
    registry = MessageRegistry()
    try:
        registry.load()
    except Exception as e:
        display.error(f"加载消息注册表失败: {e}")
        display.info("提示: 请先运行 --compile 编译 proto 文件")
        sys.exit(1)

    # ── 创建连接 ──
    conn = GameConnection()
    heartbeat = HeartbeatManager(conn)

    # ── 登录 ──
    login_ok = False

    if args.server_url:
        # HTTP 登录模式
        if not args.account:
            display.error("HTTP 登录模式需要 --account 参数")
            sys.exit(1)
        try:
            login_ok = login_http(
                conn, registry,
                args.server_url, args.platform, args.channel,
                args.account, args.token or "",
                args.server_id,
            )
        except Exception as e:
            display.error(f"登录失败: {e}")
            sys.exit(1)
    else:
        # 直连模式（有默认值兜底，不需要手动传参）
        try:
            login_ok = login_direct(
                conn, registry, args.ip, args.port,
                args.uin, args.server_id, args.sign or "",
            )
        except Exception as e:
            display.error(f"连接失败: {e}")
            sys.exit(1)

    if not login_ok:
        display.error("登录失败")
        conn.disconnect()
        sys.exit(1)
    
    # 构造 CSLogin
    cs_login_cls = registry.get_cs_class("GetUserInfo")
    if not cs_login_cls:
        display.error("找不到 CSGetUserInfo 类，请检查 proto 编译")
        return False

    get_user_msg = cs_login_cls()

    # 发送
    msg_id = MESSAGE_DEFINE["GetUserInfo"]
    body = get_user_msg.SerializeToString()
    display.print_message_detail("CSLogin", msg_id, get_user_msg)
    conn.send_message(msg_id, body)

    # ── 启动心跳 ──
    if not args.no_heartbeat:
        heartbeat.start()

    # ── 进入运行模式 ──
    try:
        if args.batch:
            runner = BatchRunner(conn, registry, heartbeat)
            passed, failed = runner.run(args.batch)
            sys.exit(0 if failed == 0 else 1)
        else:
            interactive = InteractiveMode(conn, registry, heartbeat)
            interactive.start()
    except KeyboardInterrupt:
        print()
    finally:
        # 优雅退出: 发送 CSLogout
        display.info("正在断开连接 ...")
        try:
            logout_id = MESSAGE_DEFINE["Logout"]
            # 手动编码空的 CSLogout
            conn.send_message(logout_id, b"")
        except Exception:
            pass

        heartbeat.stop()
        conn.disconnect()
        display.info("已退出")


if __name__ == "__main__":
    main()
