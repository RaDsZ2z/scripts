# -*- coding: utf-8 -*-
"""
彩色控制台输出。

配色方案:
  青色 = 发送 (CS)
  绿色 = 接收 (SC)
  黄色 = 心跳 / 警告
  红色 = 错误
  灰色 = 调试
  白色 = 普通信息
"""

import json
import base64
import datetime

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# 如果没有 colorama，用空字符串代替
if not HAS_COLORAMA:
    class _FakeColor:
        def __getattr__(self, _):
            return ""
    Fore = _FakeColor()
    Style = _FakeColor()


_use_color = True


def enable_color(enabled):
    global _use_color
    _use_color = enabled


def _ts():
    """时间戳前缀"""
    return datetime.datetime.now().strftime("%H:%M:%S")


def info(msg):
    """普通信息"""
    print(f"{Fore.WHITE}[{_ts()}] {msg}{Style.RESET_ALL}")


def sent(msg, msg_id=None, seq=None):
    """发送的消息（青色）"""
    tag = f"{Fore.CYAN}[{_ts()}] >> "
    if msg_id is not None:
        tag += f"{msg} ({msg_id})"
    else:
        tag += msg
    if seq is not None:
        tag += f" [seq={seq}]"
    print(tag + Style.RESET_ALL)


def received(msg, msg_id=None, seq=None):
    """接收的消息（绿色）"""
    tag = f"{Fore.GREEN}[{_ts()}] << "
    if msg_id is not None:
        tag += f"{msg} ({msg_id})"
    else:
        tag += msg
    if seq is not None:
        tag += f" [seq={seq}]"
    print(tag + Style.RESET_ALL)


def heartbeat(msg):
    """心跳消息（黄色）"""
    print(f"{Fore.YELLOW}[{_ts()}] [HB] {msg}{Style.RESET_ALL}")


def warn(msg):
    """警告（黄色）"""
    print(f"{Fore.YELLOW}[{_ts()}] [警告] {msg}{Style.RESET_ALL}")


def error(msg):
    """错误（红色）"""
    print(f"{Fore.RED}[{_ts()}] [错误] {msg}{Style.RESET_ALL}")


def debug(msg):
    """调试信息（灰色/暗色）"""
    print(f"{Fore.LIGHTBLACK_EX}[{_ts()}] {msg}{Style.RESET_ALL}")


def success(msg):
    """成功信息（绿色粗体）"""
    print(f"{Fore.GREEN}[{_ts()}] {msg}{Style.RESET_ALL}")


def separator():
    """分隔线"""
    print(f"{Fore.LIGHTBLACK_EX}{'─' * 60}{Style.RESET_ALL}")


def format_proto_message(msg):
    """
    将 protobuf 消息格式化为可读的多行字符串。

    :param msg: protobuf 消息实例
    :return: 格式化后的字符串列表
    """
    lines = []
    for field in msg.DESCRIPTOR.fields:
        value = getattr(msg, field.name, None)
        if value is None:
            continue

        # bytes 字段显示 base64
        if field.type == field.TYPE_BYTES:
            if isinstance(value, bytes) and len(value) > 0:
                display = base64.b64encode(value).decode("ascii")
                if len(display) > 60:
                    display = display[:57] + "..."
                lines.append(f"  {field.name}: <bytes:{len(value)}> {display}")
            else:
                lines.append(f"  {field.name}: <empty>")
            continue

        # repeated 字段
        if field.label == field.LABEL_REPEATED:
            if len(value) == 0:
                continue
            if len(value) <= 5:
                items = []
                for item in value:
                    items.append(_format_field_value(item, field))
                lines.append(f"  {field.name}: [{', '.join(items)}]")
            else:
                lines.append(f"  {field.name}: [{len(value)} items]")
            continue

        # enum 字段显示名称
        if field.type == field.TYPE_ENUM:
            enum_val = field.enum_type.values_by_number.get(value)
            name = enum_val.name if enum_val else str(value)
            lines.append(f"  {field.name}: {name} ({value})")
            continue

        # 普通字段
        display_val = _format_field_value(value, field)
        if display_val is not None:
            lines.append(f"  {field.name}: {display_val}")

    return lines


def _format_field_value(value, field):
    """格式化单个字段值"""
    if hasattr(value, "DESCRIPTOR"):
        # 嵌套消息，递归缩进
        sub_lines = format_proto_message(value)
        return "\n" + "\n".join("  " + l for l in sub_lines)

    if isinstance(value, bytes):
        if len(value) == 0:
            return "<empty>"
        b64 = base64.b64encode(value).decode("ascii")
        if len(b64) > 50:
            b64 = b64[:47] + "..."
        return f"<bytes:{len(value)}> {b64}"

    if isinstance(value, bool):
        return str(value).lower()

    return repr(value)


def print_message_detail(name, msg_id, msg, seq=None):
    """打印完整的消息详情"""
    if name.startswith("CS"):
        sent(name, msg_id, seq)
    else:
        received(name, msg_id, seq)

    if msg is not None:
        for line in format_proto_message(msg):
            print(line)
    print()  # 空行分隔
