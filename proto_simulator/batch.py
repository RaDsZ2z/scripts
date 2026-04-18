# -*- coding: utf-8 -*-
"""
批量测试模式。

从 JSON 文件读取测试脚本，顺序执行每个步骤:
  send → wait_for → assert
"""

import json
import queue
import threading
import time

from .config import MESSAGE_DEFINE
from . import display
from .interactive import InteractiveMode


class BatchRunner:
    """批量测试执行器"""

    def __init__(self, conn, registry, heartbeat):
        self._conn = conn
        self._registry = registry
        self._heartbeat = heartbeat
        self._msg_queue = queue.Queue(maxsize=256)
        self._running = False

    def run(self, script_path):
        """
        执行批量测试脚本。

        :param script_path: JSON 脚本文件路径
        :return: (passed, failed) 步骤计数
        """
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        steps = script.get("steps", [])
        if not steps:
            display.warn("脚本中没有测试步骤")
            return 0, 0

        display.info(f"批量测试: {len(steps)} 个步骤")

        # 启动消息接收
        self._running = True
        self._conn.set_message_callback(self._on_message)

        passed = 0
        failed = 0

        try:
            for i, step in enumerate(steps):
                step_name = step.get("name", f"步骤 {i + 1}")
                display.separator()
                display.info(f"[{i + 1}/{len(steps)}] {step_name}")

                try:
                    if not self._execute_step(step):
                        failed += 1
                        display.error(f"  失败")
                        if step.get("abort_on_fail", False):
                            display.error("  终止执行")
                            break
                    else:
                        passed += 1
                        display.success(f"  通过")
                except Exception as e:
                    failed += 1
                    display.error(f"  异常: {e}")

        finally:
            self._running = False
            self._conn.set_message_callback(None)

        display.separator()
        display.info(f"测试完成: {passed} 通过, {failed} 失败")
        return passed, failed

    def _on_message(self, header, body):
        """收到消息入队"""
        self._msg_queue.put((header, body))

    def _execute_step(self, step):
        """执行单个测试步骤"""
        # 发送消息
        send_name = step.get("send")
        if not send_name:
            display.warn("  步骤缺少 send 字段，跳过")
            return True

        params = step.get("params", {})
        cs_cls = self._registry.get_cs_class(send_name)
        if not cs_cls:
            display.error(f"  未找到协议: {send_name}")
            return False

        msg_id = self._registry.get_msg_id(send_name)
        if msg_id is None:
            display.error(f"  未找到消息 ID: {send_name}")
            return False

        # 构建并发送
        from .interactive import InteractiveMode
        interactive = InteractiveMode(self._conn, self._registry, self._heartbeat)
        msg = interactive._build_proto_message(cs_cls, params)
        body = msg.SerializeToString()
        seq = self._conn.send_message(msg_id, body)
        display.sent(f"CS{send_name}", msg_id, seq)

        # 等待响应
        wait_for = step.get("wait_for")
        if not wait_for:
            return True

        timeout = step.get("timeout", 10)

        # 去掉 SC 前缀
        if wait_for.startswith("SC"):
            enum_name = wait_for[2:]
        else:
            enum_name = wait_for

        expected_id = MESSAGE_DEFINE.get(enum_name)
        if expected_id is None:
            display.error(f"  未找到等待协议: {wait_for}")
            return False

        display.info(f"  等待 {wait_for} (超时 {timeout}s) ...")

        # 从队列中等待目标消息
        deadline = time.time() + timeout
        received_msg = None

        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                header, resp_body = self._msg_queue.get(timeout=min(remaining, 1))
            except queue.Empty:
                continue

            if header.message_id == expected_id:
                received_msg = (header, resp_body)
                break
            else:
                # 非目标消息，打印并继续等待
                sc_name = self._registry.get_sc_name_by_id(header.message_id)
                display.received(sc_name, header.message_id, header.sequence)

        if received_msg is None:
            display.error(f"  等待 {wait_for} 超时")
            return False

        header, resp_body = received_msg
        sc_cls = self._registry.get_sc_class_by_id(expected_id)

        if sc_cls:
            sc_msg = sc_cls()
            try:
                sc_msg.ParseFromString(resp_body)
                display.received(f"SC{enum_name}", expected_id, header.sequence)

                # 执行断言
                asserts = step.get("assert", [])
                if isinstance(asserts, dict):
                    asserts = [asserts]

                for assertion in asserts:
                    if not self._assert_field(sc_msg, assertion):
                        return False

            except Exception as e:
                display.error(f"  解析 {wait_for} 失败: {e}")
                return False
        else:
            display.received(f"SC{enum_name}", expected_id, header.sequence)

        return True

    def _assert_field(self, msg, assertion):
        """断言消息字段值"""
        field_path = assertion.get("field", "")
        op = assertion.get("op", "==")
        expected = assertion.get("value")

        # 支持嵌套字段路径: "info.level"
        value = msg
        for part in field_path.split("."):
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                display.error(f"  断言失败: 字段路径 '{field_path}' 无效")
                return False

        result = self._compare(value, op, expected)
        if not result:
            display.error(f"  断言失败: {field_path} {op} {expected} (实际: {value})")
        else:
            display.success(f"  断言通过: {field_path} {op} {expected}")

        return result

    def _compare(self, actual, op, expected):
        """比较操作"""
        if op == "==":
            return actual == expected
        elif op == "!=":
            return actual != expected
        elif op == ">":
            return actual > expected
        elif op == ">=":
            return actual >= expected
        elif op == "<":
            return actual < expected
        elif op == "<=":
            return actual <= expected
        elif op == "contains":
            return expected in actual
        else:
            display.warn(f"  未知比较操作: {op}")
            return True
