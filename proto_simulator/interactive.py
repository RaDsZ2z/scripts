# -*- coding: utf-8 -*-
"""
交互式 REPL 模式。

支持命令:
  send <MsgName> [JSON]     发送 CS 消息
  help [keyword]            列出协议（可按关键词过滤）
  status                    显示连接状态
  wait <MsgName> [timeout]  等待指定的 SC 消息
  heartbeat [on|off|now]   心跳控制
  quit / exit               退出
"""

import base64
import json
import sys
import time
import threading

from google.protobuf.descriptor import FieldDescriptor as _FD

from .config import MESSAGE_DEFINE
from . import display


class InteractiveMode:
    """交互式命令处理器"""

    def __init__(self, conn, registry, heartbeat):
        self._conn = conn
        self._registry = registry
        self._heartbeat = heartbeat
        self._running = False
        self._pending_waits = {}  # msg_id → threading.Event

    def start(self):
        """进入交互循环"""
        self._running = True

        # 设置消息回调
        self._conn.set_message_callback(self._on_message)

        display.separator()
        display.info("进入交互模式。输入 help 查看命令，quit 退出。")
        display.separator()

        try:
            while self._running and self._conn.connected:
                try:
                    cmd = input(f"{display.Fore.WHITE}proto>{display.Style.RESET_ALL} ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not cmd:
                    continue

                self._handle_command(cmd)
        finally:
            self._running = False
            self._conn.set_message_callback(None)

    def _on_message(self, header, body):
        """收到消息的回调（在接收线程中执行）"""
        msg_id = header.message_id
        sc_name = self._registry.get_sc_name_by_id(msg_id)
        sc_cls = self._registry.get_sc_class_by_id(msg_id)

        # 心跳特殊处理
        if msg_id == MESSAGE_DEFINE.get("HeartBeat"):
            if sc_cls:
                msg = sc_cls()
                try:
                    msg.ParseFromString(body)
                    delta = int(time.time() * 1000) - msg.send_millisecond
                    display.heartbeat(f"响应 延迟: {delta}ms")
                except Exception:
                    pass
            return

        # NotifyFail 特殊处理
        if msg_id == MESSAGE_DEFINE.get("NotifyFail"):
            if sc_cls:
                msg = sc_cls()
                try:
                    msg.ParseFromString(body)
                    display.error(f"NotifyFail: msg_id={msg.message_id}, result_id={msg.result_id}")
                except Exception:
                    display.error("NotifyFail (解析失败)")
            return

        # 普通消息
        if sc_cls:
            msg = sc_cls()
            try:
                msg.ParseFromString(body)
                display.print_message_detail(sc_name, msg_id, msg, header.sequence)
            except Exception as e:
                display.error(f"解析 {sc_name} 失败: {e}")
                display.info(f"  原始数据: {body[:64].hex()}")
        else:
            display.received(f"Unknown({msg_id})", msg_id, header.sequence)
            display.info(f"  原始数据 ({len(body)} bytes): {body[:64].hex()}")

        # 检查是否有等待中的 wait
        if msg_id in self._pending_waits:
            event = self._pending_waits.pop(msg_id)
            event.set()

    def _handle_command(self, cmd_line):
        """解析并执行命令"""
        parts = cmd_line.split(None, 1)
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            self._running = False

        elif cmd == "send":
            self._cmd_send(args)

        elif cmd in ("help", "h"):
            self._cmd_help(args)

        elif cmd in ("desc", "describe", "d"):
            self._cmd_desc(args)

        elif cmd == "status":
            self._cmd_status()

        elif cmd == "wait":
            self._cmd_wait(args)

        elif cmd == "heartbeat":
            self._cmd_heartbeat(args)

        else:
            display.error(f"未知命令: {cmd}。输入 help 查看可用命令。")

    def _cmd_send(self, args):
        """发送消息"""
        parts = args.split(None, 1)
        if not parts:
            display.error("用法: send <MsgName> [JSON]")
            return

        msg_name = parts[0]
        json_str = parts[1] if len(parts) > 1 else "{}"

        # 查找消息类
        cs_cls = self._registry.get_cs_class(msg_name)
        if not cs_cls:
            # 模糊搜索
            suggestions = self._registry.search_messages(msg_name)
            if suggestions:
                display.warn(f"未找到 '{msg_name}'，你是否想找:")
                for name, mid, typ in suggestions[:5]:
                    display.info(f"  {typ}: {name} ({mid})")
            else:
                display.error(f"未找到协议: {msg_name}")
            return

        # 解析 JSON 参数
        try:
            params = json.loads(json_str)
        except json.JSONDecodeError as e:
            display.error(f"JSON 解析失败: {e}")
            return

        # 构造 protobuf 消息
        try:
            msg = self._build_proto_message(cs_cls, params)
        except Exception as e:
            display.error(f"构造消息失败: {e}")
            return

        # 获取消息 ID
        msg_id = self._registry.get_msg_id(msg_name)
        if msg_id is None:
            display.error(f"找不到消息 ID: {msg_name}")
            return

        # 发送
        try:
            body = msg.SerializeToString()
            seq = self._conn.send_message(msg_id, body)
            display.print_message_detail(f"CS{msg_name}", msg_id, msg, seq)
        except Exception as e:
            display.error(f"发送失败: {e}")
            self._running = False

    def _cmd_help(self, args):
        """显示帮助"""
        if not args:
            display.info("可用命令:")
            display.info("  send <Msg> [JSON]        发送 CS 消息")
            display.info("  desc <Msg>               查看协议字段结构")
            display.info("  wait <Msg> [timeout]     等待 SC 消息")
            display.info("  help [keyword]           搜索协议")
            display.info("  heartbeat [on|off|now]   心跳控制")
            display.info("  status                   连接状态")
            display.info("  quit                     退出")
            return

        # 搜索协议
        results = self._registry.search_messages(args)
        if results:
            display.info(f"匹配 '{args}' 的协议 ({len(results)} 个):")
            for name, mid, typ in results[:30]:
                display.info(f"  {typ:4s}  {name:40s} ({mid})")
        else:
            display.warn(f"没有匹配 '{args}' 的协议")

    def _cmd_desc(self, args):
        """查看协议字段结构"""
        if not args:
            display.error("用法: desc <MsgName>  例如: desc FarmlandStart")
            return

        # 找 CS 和 SC 两个类
        cs_cls = self._registry.get_cs_class(args)
        sc_cls = self._registry.get_sc_class(args)
        msg_id = self._registry.get_msg_id(args)

        if not cs_cls and not sc_cls:
            display.error(f"未找到协议: {args}")
            return

        display.separator()
        if msg_id is not None:
            display.info(f"协议: {args}  (ID: {msg_id})")
        else:
            display.info(f"协议: {args}")

        if cs_cls:
            display.info("")
            display.info(f"CS{args} (客户端 → 服务器):")
            self._print_fields(cs_cls, indent="  ")

        if sc_cls:
            display.info("")
            display.info(f"SC{args} (服务器 → 客户端):")
            self._print_fields(sc_cls, indent="  ")

        display.info("")
        if cs_cls:
            display.info("发送示例:")
            display.info(f'  send {args} {{}}')
            # 带默认值的示例
            sample = self._build_sample(cs_cls)
            if sample != "{}":
                display.info(f'  send {args} {sample}')
        display.separator()

    def _print_fields(self, cls, indent=""):
        """打印 protobuf 消息的字段信息"""
        _type_names = {
            _FD.TYPE_DOUBLE: "double",
            _FD.TYPE_FLOAT: "float",
            _FD.TYPE_INT64: "int64",
            _FD.TYPE_UINT64: "uint64",
            _FD.TYPE_INT32: "int32",
            _FD.TYPE_FIXED64: "fixed64",
            _FD.TYPE_FIXED32: "fixed32",
            _FD.TYPE_BOOL: "bool",
            _FD.TYPE_STRING: "string",
            _FD.TYPE_BYTES: "bytes",
            _FD.TYPE_UINT32: "uint32",
            _FD.TYPE_SFIXED32: "sfixed32",
            _FD.TYPE_SFIXED64: "sfixed64",
            _FD.TYPE_SINT32: "sint32",
            _FD.TYPE_SINT64: "sint64",
            _FD.TYPE_ENUM: "enum",
            _FD.TYPE_MESSAGE: "message",
        }

        for field in cls.DESCRIPTOR.fields:
            type_name = _type_names.get(field.type, str(field.type))
            repeated = "repeated " if field.label == field.LABEL_REPEATED else ""

            if field.type == field.TYPE_ENUM and field.enum_type:
                enum_values = [v.name for v in field.enum_type.values]
                type_name = f"enum({', '.join(enum_values[:5])}{'...' if len(enum_values) > 5 else ''})"

            if field.message_type:
                display.info(f"{indent}{field.name}: {repeated}message")
                self._print_fields_by_descriptor(field.message_type, indent + "  ")
            else:
                display.info(f"{indent}{field.name}: {repeated}{type_name}  (field {field.number})")

    def _print_fields_by_descriptor(self, msg_descriptor, indent=""):
        """递归打印嵌套消息字段"""
        _type_names = {
            _FD.TYPE_DOUBLE: "double",
            _FD.TYPE_FLOAT: "float",
            _FD.TYPE_INT64: "int64",
            _FD.TYPE_UINT64: "uint64",
            _FD.TYPE_INT32: "int32",
            _FD.TYPE_FIXED64: "fixed64",
            _FD.TYPE_FIXED32: "fixed32",
            _FD.TYPE_BOOL: "bool",
            _FD.TYPE_STRING: "string",
            _FD.TYPE_BYTES: "bytes",
            _FD.TYPE_UINT32: "uint32",
            _FD.TYPE_SFIXED32: "sfixed32",
            _FD.TYPE_SFIXED64: "sfixed64",
            _FD.TYPE_SINT32: "sint32",
            _FD.TYPE_SINT64: "sint64",
            _FD.TYPE_ENUM: "enum",
            _FD.TYPE_MESSAGE: "message",
        }

        for field in msg_descriptor.fields:
            type_name = _type_names.get(field.type, str(field.type))
            repeated = "repeated " if field.label == field.LABEL_REPEATED else ""

            if field.type == field.TYPE_ENUM and field.enum_type:
                enum_values = [v.name for v in field.enum_type.values]
                type_name = f"enum({', '.join(enum_values[:5])}{'...' if len(enum_values) > 5 else ''})"

            if field.message_type:
                display.info(f"{indent}{field.name}: {repeated}message")
                self._print_fields_by_descriptor(field.message_type, indent + "  ")
            else:
                display.info(f"{indent}{field.name}: {repeated}{type_name}  (field {field.number})")

    def _build_sample(self, cls):
        """根据字段结构生成 JSON 示例"""
        import json as _json
        sample = {}
        for field in cls.DESCRIPTOR.fields:
            if field.type == field.TYPE_MESSAGE:
                continue  # 跳过嵌套消息
            if field.label == field.LABEL_REPEATED:
                continue  # 跳过 repeated
            if field.type == field.TYPE_BOOL:
                sample[field.name] = False
            elif field.type == field.TYPE_STRING:
                sample[field.name] = ""
            elif field.type == field.TYPE_BYTES:
                sample[field.name] = ""
            elif field.type in (_FD.TYPE_INT32, _FD.TYPE_INT64,
                                _FD.TYPE_UINT32, _FD.TYPE_UINT64):
                sample[field.name] = 0
            elif field.type in (_FD.TYPE_FLOAT, _FD.TYPE_DOUBLE):
                sample[field.name] = 0.0
        if not sample:
            return "{}"
        return _json.dumps(sample, ensure_ascii=False)

    def _cmd_status(self):
        """显示连接状态"""
        display.info(f"连接状态: {'已连接' if self._conn.connected else '已断开'}")
        display.info(f"UIN: {self._conn.uin}")
        display.info(f"服务器 ID: {self._conn.server_id}")
        display.info(f"序列号: {self._conn._sequence}")
        display.info(f"心跳: {'运行中' if self._heartbeat._running else '已停止'}")

    def _cmd_wait(self, args):
        """等待特定 SC 消息"""
        parts = args.split(None, 1)
        if not parts:
            display.error("用法: wait <MsgName> [timeout_seconds]")
            return

        msg_name = parts[0]
        timeout = float(parts[1]) if len(parts) > 1 else 30

        # 去掉 SC 前缀
        if msg_name.startswith("SC"):
            enum_name = msg_name[2:]
        else:
            enum_name = msg_name

        msg_id = MESSAGE_DEFINE.get(enum_name)
        if msg_id is None:
            display.error(f"未找到协议: {msg_name}")
            return

        display.info(f"等待 {msg_name} (ID: {msg_id})，超时 {timeout}s ...")

        event = threading.Event()
        self._pending_waits[msg_id] = event

        if event.wait(timeout=timeout):
            display.success(f"收到 {msg_name}")
        else:
            self._pending_waits.pop(msg_id, None)
            display.warn(f"等待 {msg_name} 超时")

    def _cmd_heartbeat(self, args):
        """心跳控制"""
        if not args or args == "on":
            self._heartbeat.start()
        elif args == "off":
            self._heartbeat.stop()
        elif args == "now":
            self._heartbeat.send_now()
        else:
            display.info("用法: heartbeat [on|off|now]")

    # ── Protobuf 消息构建 ─────────────────────────────

    def _build_proto_message(self, cls, params):
        """
        从 JSON params dict 构建 protobuf 消息。

        特殊处理:
        - bytes 字段: 从 base64 字符串解码
        - repeated 字段: 从 JSON 数组构建
        - 嵌套消息: 从 JSON dict 递归构建
        """
        msg = cls()

        for field in cls.DESCRIPTOR.fields:
            if field.name not in params:
                continue
            value = params[field.name]
            self._set_field(msg, field, value)

        return msg

    def _set_field(self, msg, field, value):
        """设置 protobuf 消息的某个字段"""
        if field.label == field.LABEL_REPEATED:
            repeated = getattr(msg, field.name)
            for item in value:
                if field.message_type:
                    sub_msg = repeated.add()
                    self._fill_message(sub_msg, field.message_type, item)
                else:
                    repeated.append(self._convert_scalar(item, field))
            return

        if field.message_type:
            sub_msg = getattr(msg, field.name)
            self._fill_message(sub_msg, field.message_type, value)
            return

        # bytes 字段
        if field.type == field.TYPE_BYTES:
            if isinstance(value, str):
                setattr(msg, field.name, base64.b64decode(value))
            elif isinstance(value, bytes):
                setattr(msg, field.name, value)
            return

        # 标量字段
        setattr(msg, field.name, self._convert_scalar(value, field))

    def _fill_message(self, msg, msg_descriptor, data):
        """填充嵌套消息"""
        for field in msg_descriptor.fields:
            if field.name not in data:
                continue
            self._set_field(msg, field, data[field.name])

    def _convert_scalar(self, value, field):
        """转换 JSON 标量值为 protobuf 字段值"""
        if field.type in (_FD.TYPE_INT32, _FD.TYPE_INT64,
                          _FD.TYPE_SINT32, _FD.TYPE_SINT64,
                          _FD.TYPE_SFIXED32, _FD.TYPE_SFIXED64):
            return int(value)
        if field.type in (_FD.TYPE_UINT32, _FD.TYPE_UINT64,
                          _FD.TYPE_FIXED32, _FD.TYPE_FIXED64):
            return int(value)
        if field.type == _FD.TYPE_FLOAT:
            return float(value)
        if field.type == _FD.TYPE_DOUBLE:
            return float(value)
        if field.type == _FD.TYPE_BOOL:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        if field.type == _FD.TYPE_STRING:
            return str(value)
        if field.type == _FD.TYPE_ENUM:
            return int(value)
        return value
