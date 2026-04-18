# -*- coding: utf-8 -*-
"""
22 字节包头编解码 + TCP 收包

包头结构（大端序，共 22 字节）:
  [0:4]  PacketLength    int32   总包长（含包头）
  [4:5]  HeaderLength    byte    固定 22
  [5:6]  Flag            byte    加密标志，0=无加密
  [6:8]  ServiceType     ushort  服务类型 (Logic=3)
  [8:12] Uin             int32   玩家ID
  [12:16] GroupId        int32   服务器ID
  [16:18] MessageId      ushort  协议ID
  [18:22] Sequence       int32   序列号
"""

import struct
from collections import namedtuple

from .config import HEADER_LENGTH, HEADER_STRUCT_FMT

PacketHeader = namedtuple("PacketHeader", [
    "packet_length",  # 总长（含头），int
    "header_length",  # 包头长，int
    "flag",           # 加密标志，int
    "service_type",   # 服务类型，int
    "uin",            # 玩家ID，int
    "group_id",       # 服务器ID，int
    "message_id",     # 协议ID，int
    "sequence",       # 序列号，int
])


def encode_packet(service_type, uin, group_id, message_id, sequence, body_bytes):
    """
    编码一个完整网络包（包头 + 包体）。

    :param service_type: 服务类型 (ushort)
    :param uin: 玩家 ID (int32)
    :param group_id: 服务器 ID (int32)
    :param message_id: 协议 ID (ushort)
    :param sequence: 序列号 (int32)
    :param body_bytes: Protobuf 序列化后的包体 bytes
    :return: 完整包 bytes
    """
    total_length = HEADER_LENGTH + len(body_bytes)
    header = struct.pack(
        HEADER_STRUCT_FMT,
        total_length,     # PacketLength (uint32)
        HEADER_LENGTH,    # HeaderLength (byte)
        0,                # Flag (byte)
        service_type,     # ServiceType (ushort)
        uin,              # Uin (int32)
        group_id,         # GroupId (int32)
        message_id,       # MessageId (ushort)
        sequence,         # Sequence (int32)
    )
    return header + body_bytes


def decode_header(raw_22bytes):
    """
    解码 22 字节包头。

    :param raw_22bytes: 至少 22 字节的 bytes/memoryview
    :return: PacketHeader named tuple
    """
    values = struct.unpack(HEADER_STRUCT_FMT, raw_22bytes[:HEADER_LENGTH])
    return PacketHeader(*values)


def body_length_from_header(header):
    """
    从包头计算包体长度。
    线上的 PacketLength 含包头，包体 = PacketLength - 22。
    """
    return header.packet_length - HEADER_LENGTH


# ── TCP 收包工具 ─────────────────────────────────────

def _recv_exactly(sock, n):
    """从 socket 精确读取 n 字节，处理部分读。"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("连接已断开")
        buf.extend(chunk)
    return bytes(buf)


def recv_packet(sock):
    """
    从 TCP socket 接收一个完整网络包。

    :return: (PacketHeader, body_bytes)
    :raises ConnectionError: 连接断开
    """
    header_raw = _recv_exactly(sock, HEADER_LENGTH)
    header = decode_header(header_raw)
    blen = body_length_from_header(header)
    body = _recv_exactly(sock, blen) if blen > 0 else b""
    return header, body
