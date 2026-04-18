# -*- coding: utf-8 -*-
"""
登录流程：
  1. HTTP 登录获取连接凭证 (可选)
  2. TCP 连接
  3. 发送 CSLogin
  4. 等待 SCLogin
"""

import base64
import time

from .config import MESSAGE_DEFINE, LOGIN_TIMEOUT
from .connection import GameConnection
from . import display


def login_direct(conn, registry, ip, port, uin, server_id, sign_b64):
    """
    直连模式登录。

    :param conn: GameConnection 实例
    :param registry: MessageRegistry 实例
    :param ip: 服务器 IP
    :param port: 服务器端口
    :param uin: 玩家 UIN
    :param server_id: 服务器 ID
    :param sign_b64: Base64 编码的签名
    :return: True 登录成功
    """
    conn.uin = uin
    conn.server_id = server_id

    # 连接 TCP
    display.info(f"正在连接 {ip}:{port} ...")
    conn.connect(ip, port)
    display.success("TCP 连接成功")

    # 构造 CSLogin
    cs_login_cls = registry.get_cs_class("Login")
    if not cs_login_cls:
        display.error("找不到 CSLogin 类，请检查 proto 编译")
        return False

    login_msg = cs_login_cls()
    if sign_b64:
        login_msg.signature = base64.b64decode(sign_b64)
    login_msg.device_id = "proto_simulator"
    login_msg.pkg_version = "1.0.0"
    login_msg.res_version = -1
    login_msg.fight_version = 0
    login_msg.is_reconnect = False
    login_msg.sdk_property = ""

    # 发送
    msg_id = MESSAGE_DEFINE["Login"]
    body = login_msg.SerializeToString()
    display.print_message_detail("CSLogin", msg_id, login_msg)
    conn.send_message(msg_id, body)

    # 等待 SCLogin
    display.info("等待 SCLogin 响应 ...")
    try:
        header, resp_body = conn.recv_message(timeout=LOGIN_TIMEOUT)
    except Exception as e:
        display.error(f"等待 SCLogin 超时或连接断开: {e}")
        return False

    sc_name = registry.get_sc_name_by_id(header.message_id)
    sc_cls = registry.get_sc_class_by_id(header.message_id)

    if sc_cls:
        sc_msg = sc_cls()
        try:
            sc_msg.ParseFromString(resp_body)
        except Exception as e:
            display.error(f"解析 SCLogin 失败: {e}")
            return False

        display.print_message_detail(sc_name, header.message_id, sc_msg, header.sequence)

        if header.message_id == msg_id:
            display.success("登录成功!")
            return True
        elif header.message_id == MESSAGE_DEFINE.get("NotifyFail"):
            display.error("登录失败: 服务器返回 NotifyFail")
            return False
    else:
        display.received(sc_name, header.message_id, header.sequence)
        display.info(f"  原始数据 ({len(resp_body)} bytes): {resp_body[:64].hex()}...")

    return header.message_id == msg_id


def login_http(conn, registry, server_url, platform, channel, account, token, server_id=None):
    """
    HTTP 登录流程 (3步)。

    :return: True 登录成功
    """
    try:
        import requests
    except ImportError:
        display.error("需要 requests 库，请运行: pip install requests")
        return False

    # Step 1: 获取服务器配置
    display.info("Step 1: 获取服务器配置 ...")
    try:
        resp = requests.get(
            f"{server_url}/service/domain",
            params={"channel": channel, "version": "1.0.0", "res_tag": ""},
            timeout=10,
        )
        config_data = resp.json()
    except Exception as e:
        display.error(f"获取服务器配置失败: {e}")
        return False

    if not config_data.get("status"):
        display.error(f"服务器配置请求失败: {config_data.get('message')}")
        return False

    servers_url = config_data["data"].get("servers_url")
    login_url = config_data["data"].get("login_url")
    display.success(f"  servers_url: {servers_url}")
    display.success(f"  login_url: {login_url}")

    # Step 2: 获取服务器列表
    display.info("Step 2: 获取服务器列表 ...")
    try:
        resp = requests.get(
            servers_url,
            params={"platform": platform, "channel": channel, "account": account, "token": token},
            timeout=10,
        )
        group_data = resp.json()
    except Exception as e:
        display.error(f"获取服务器列表失败: {e}")
        return False

    if not group_data.get("status"):
        display.error(f"服务器列表请求失败: {group_data.get('message')}")
        return False

    # 解析服务器列表
    servers = []
    for group in group_data.get("data", {}).get("servers", []):
        for srv in group.get("group_servers", []):
            servers.append(srv)
            display.info(f"  服务器 {srv['id']}: {srv['name']} ({srv.get('prefix', '')})")

    if not servers:
        display.error("没有可用的服务器")
        return False

    # 选择服务器
    target = None
    if server_id is not None:
        for srv in servers:
            if srv["id"] == server_id:
                target = srv
                break
        if not target:
            display.error(f"未找到服务器 ID: {server_id}")
            return False
    else:
        target = servers[0]

    display.info(f"选择服务器: {target['name']} (ID: {target['id']})")
    login_token = target.get("login_token", "")
    extend = group_data.get("data", {}).get("extend", "")

    # Step 3: 获取登录凭证
    display.info("Step 3: 获取登录凭证 ...")
    try:
        resp = requests.get(
            login_url,
            params={
                "platform": platform,
                "channel": channel,
                "account": account,
                "server": target["id"],
                "login_token": login_token,
                "extend": extend,
            },
            timeout=10,
        )
        login_data = resp.json()
    except Exception as e:
        display.error(f"获取登录凭证失败: {e}")
        return False

    if not login_data.get("status"):
        display.error(f"登录请求失败: {login_data.get('message')}")
        return False

    data = login_data["data"]
    ip = data["ip"]
    port = data["port"]
    uin = data["user_uin"]
    sign = data.get("sign", "")
    sid = data.get("server_id", target["id"])

    display.success(f"  UIN: {uin}")
    display.success(f"  服务器: {ip}:{port}")
    display.success(f"  Sign: {sign[:40]}...")

    # 直连登录
    return login_direct(conn, registry, ip, port, uin, sid, sign)
