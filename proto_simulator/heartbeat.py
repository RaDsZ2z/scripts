# -*- coding: utf-8 -*-
"""
自动心跳管理器。

每 30 秒发送 CSHeartBeat，与客户端的 HeartBeatInterval = 30 一致。
"""

import threading
import time

from .config import MESSAGE_DEFINE, HEARTBEAT_INTERVAL
from . import display


class HeartbeatManager:
    """后台心跳线程"""

    def __init__(self, conn):
        """
        :param conn: GameConnection 实例
        """
        self._conn = conn
        self._running = False
        self._thread = None
        self._interval = HEARTBEAT_INTERVAL

    def start(self):
        """启动心跳"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        display.heartbeat("心跳已启动")

    def stop(self):
        """停止心跳"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        display.heartbeat("心跳已停止")

    def _loop(self):
        """心跳循环"""
        msg_id = MESSAGE_DEFINE["HeartBeat"]

        while self._running and self._conn.connected:
            try:
                # 构造 CSHeartBeat
                # CSHeartBeat 只有一个字段: send_millisecond (int64)
                # 用 int(time.time() * 1000) 模拟 Environment.TickCount
                import struct
                # 手动编码 protobuf: field 1, varint = int(time.time()*1000)
                ts = int(time.time() * 1000)
                # protobuf varint encoding for field 1 (wire type 0): tag=0x08
                body = b"\x08" + _encode_varint(ts)

                self._conn.send_message(msg_id, body)
                display.debug("心跳已发送")
            except Exception as e:
                if self._running:
                    display.heartbeat(f"心跳发送失败: {e}")
                break

            # 等待 interval，每秒检查一次 running 标志
            for _ in range(self._interval):
                if not self._running:
                    return
                time.sleep(1)

    def send_now(self):
        """立即发送一次心跳"""
        msg_id = MESSAGE_DEFINE["HeartBeat"]
        ts = int(time.time() * 1000)
        body = b"\x08" + _encode_varint(ts)
        self._conn.send_message(msg_id, body)
        display.heartbeat("手动心跳已发送")


def _encode_varint(value):
    """编码 protobuf varint"""
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)
