# -*- coding: utf-8 -*-
"""
TCP 连接管理器：后台接收线程 + 发送锁。
"""

import queue
import socket
import threading
import time

from .packet import encode_packet, recv_packet, PacketHeader
from .config import SERVICE_TYPE_LOGIC, TCP_RECV_BUFFER


class GameConnection:
    """TCP 连接到游戏服务器，后台线程自动接收消息。"""

    def __init__(self):
        self._sock = None
        self._connected = False
        self._recv_thread = None
        self._running = False
        self._send_lock = threading.Lock()
        self._sequence = 0
        self._recv_queue = queue.Queue(maxsize=1024)

        # 连接参数
        self.uin = 0
        self.server_id = 0
        self.service_type = SERVICE_TYPE_LOGIC

        # 回调
        self.on_disconnect = None  # callable()

    @property
    def connected(self):
        return self._connected

    def connect(self, ip, port, timeout=10):
        """
        连接到游戏服务器。

        :param ip: 服务器 IP
        :param port: 服务器端口
        :param timeout: 连接超时秒数
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            self._sock.settimeout(timeout)
            self._sock.connect((ip, port))
        except (socket.error, OSError) as e:
            self._sock.close()
            self._sock = None
            raise ConnectionError(f"连接 {ip}:{port} 失败: {e}")

        # 连接成功后设置较长的 socket 超时，方便 disconnect() 能打断 recv
        self._sock.settimeout(5)

        self._connected = True
        self._running = True

        # 启动接收线程
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def send_message(self, message_id, proto_body_bytes, sequence=None):
        """
        发送一个协议消息。

        :param message_id: 协议 ID (ushort)
        :param proto_body_bytes: Protobuf 序列化后的字节
        :param sequence: 序列号，None 则自动递增
        """
        if not self._connected or not self._sock:
            raise ConnectionError("未连接")

        if sequence is None:
            self._sequence += 1
            sequence = self._sequence

        packet = encode_packet(
            self.service_type,
            self.uin,
            self.server_id,
            message_id,
            sequence,
            proto_body_bytes,
        )

        with self._send_lock:
            try:
                self._sock.sendall(packet)
            except (socket.error, OSError) as e:
                self._connected = False
                raise ConnectionError(f"发送失败: {e}")

        return sequence

    def recv_message(self, timeout=None):
        """
        从接收队列获取一条消息（阻塞）。

        :param timeout: 超时秒数
        :return: (PacketHeader, body_bytes)
        :raises queue.Empty: 超时无消息
        :raises ConnectionError: 连接断开
        """
        try:
            return self._recv_queue.get(timeout=timeout)
        except queue.Empty:
            if not self._connected:
                raise ConnectionError("连接已断开")
            raise

    def set_message_callback(self, callback):
        """
        设置消息回调。callback(header, body_bytes) 会在收到消息时调用。
        如果设置了回调，消息不会进入队列。
        """
        self._on_message = callback

    _on_message = None

    def _recv_loop(self):
        """后台接收线程"""
        try:
            while self._running and self._connected:
                try:
                    header, body = recv_packet(self._sock)
                except socket.timeout:
                    # socket 超时是正常的（服务器没有新数据），继续等待
                    continue
                if self._on_message:
                    self._on_message(header, body)
                else:
                    try:
                        self._recv_queue.put_nowait((header, body))
                    except queue.Full:
                        try:
                            self._recv_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self._recv_queue.put_nowait((header, body))
        except ConnectionError as e:
            if self._running:
                print(f"\n[连接] 接收线程断开: {e}")
        except Exception as e:
            if self._running:
                print(f"\n[连接] 接收线程异常: {type(e).__name__}: {e}")
        finally:
            self._connected = False
            self._running = False
            if self.on_disconnect:
                self.on_disconnect()

    def disconnect(self):
        """断开连接"""
        self._running = False
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=3)

    def __del__(self):
        self.disconnect()
