# -*- coding: utf-8 -*-
"""
消息注册表：MessageId ↔ 协议名 ↔ Python protobuf 类 双向映射。

命名约定（与 SteamMessage.Define.cs 一致）：
  MessageDefine.Login → CSLogin (ClientToServer), SCLogin (ServerToClient)
"""

import importlib
import pkgutil
import re
import sys
from pathlib import Path

from .config import MESSAGE_DEFINE, ID_TO_NAME, GENERATED_DIR


class MessageRegistry:
    """协议消息注册表"""

    def __init__(self):
        # 协议名 → 消息ID
        self.name_to_id = {}        # "Login" → 10001
        # 消息ID → 枚举名
        self.id_to_name = dict(ID_TO_NAME)
        # CS 消息名 → protobuf 类
        self.cs_classes = {}        # "CSLogin" → CSLogin class
        # SC 消息名 → protobuf 类
        self.sc_classes = {}        # "SCLogin" → SCLogin class
        # 消息名 → 消息ID (含 CS/SC 前缀)
        self.msg_name_to_id = {}    # "CSLogin" → 10001, "SCLogin" → 10001
        # 消息ID → SC 类（用于反序列化收到的服务器消息）
        self.sc_id_to_class = {}    # 10001 → SCLogin class
        # 消息ID → SC 消息名
        self.sc_id_to_name = {}     # 10001 → "SCLogin"

    def load(self):
        """
        加载注册表：
        1. 从 MESSAGE_DEFINE 获取所有枚举值
        2. 动态加载 _generated 中的 protobuf 模块
        3. 发现 CS*/SC* 类并建立映射
        """
        # 建立枚举名 → ID 映射
        for name, msg_id in MESSAGE_DEFINE.items():
            self.name_to_id[name] = msg_id

        # 加载生成的 protobuf 模块
        self._load_proto_classes()

        # 建立完整映射
        for enum_name, msg_id in MESSAGE_DEFINE.items():
            cs_name = f"CS{enum_name}"
            sc_name = f"SC{enum_name}"

            if cs_name in self.cs_classes:
                self.msg_name_to_id[cs_name] = msg_id

            if sc_name in self.sc_classes:
                self.msg_name_to_id[sc_name] = msg_id
                self.sc_id_to_class[msg_id] = self.sc_classes[sc_name]
                self.sc_id_to_name[msg_id] = sc_name

        cs_count = len(self.cs_classes)
        sc_count = len(self.sc_classes)
        print(f"[注册表] 已加载 {cs_count} 个 CS 消息, {sc_count} 个 SC 消息")

    def _load_proto_classes(self):
        """动态加载 _generated 目录中的所有 _pb2 模块，发现 protobuf 消息类"""
        if not GENERATED_DIR.exists():
            print("[警告] 生成目录不存在，请先运行 --compile")
            return

        # 将 _generated 添加到 sys.path
        gen_parent = str(GENERATED_DIR.parent)
        gen_name = GENERATED_DIR.name
        if gen_parent not in sys.path:
            sys.path.insert(0, gen_parent)

        # 导入 _generated 包
        try:
            generated_pkg = importlib.import_module(gen_name)
        except ImportError as e:
            print(f"[错误] 无法导入生成模块: {e}")
            return

        # 遍历所有 _pb2 子模块
        for importer, modname, ispkg in pkgutil.iter_modules([str(GENERATED_DIR)]):
            if not modname.endswith("_pb2"):
                continue

            try:
                module = importlib.import_module(f"{gen_name}.{modname}")
            except Exception as e:
                print(f"[警告] 导入 {modname} 失败: {e}")
                continue

            # 在模块中查找 CS*/SC* 开头的类（protobuf 生成的消息类）
            for attr_name in dir(module):
                if attr_name.startswith("CS") and attr_name[2:] in MESSAGE_DEFINE:
                    cls = getattr(module, attr_name)
                    if hasattr(cls, "DESCRIPTOR"):
                        self.cs_classes[attr_name] = cls
                elif attr_name.startswith("SC") and attr_name[2:] in MESSAGE_DEFINE:
                    cls = getattr(module, attr_name)
                    if hasattr(cls, "DESCRIPTOR"):
                        self.sc_classes[attr_name] = cls

    def get_cs_class(self, name):
        """根据消息名获取 CS protobuf 类"""
        # 尝试直接匹配
        if name in self.cs_classes:
            return self.cs_classes[name]
        # 尝试加 CS 前缀
        if name in self.name_to_id:
            cs_name = f"CS{name}"
            return self.cs_classes.get(cs_name)
        return None

    def get_sc_class(self, name):
        """根据消息名获取 SC protobuf 类"""
        if name in self.sc_classes:
            return self.sc_classes[name]
        if name in self.name_to_id:
            sc_name = f"SC{name}"
            return self.sc_classes.get(sc_name)
        return None

    def get_msg_id(self, name):
        """根据消息名（CS/SC/枚举名）获取消息 ID"""
        if name in self.msg_name_to_id:
            return self.msg_name_to_id[name]
        if name in self.name_to_id:
            return self.name_to_id[name]
        return None

    def get_sc_class_by_id(self, msg_id):
        """根据消息 ID 获取 SC protobuf 类"""
        return self.sc_id_to_class.get(msg_id)

    def get_sc_name_by_id(self, msg_id):
        """根据消息 ID 获取 SC 消息名"""
        return self.sc_id_to_name.get(msg_id, f"Unknown({msg_id})")

    def search_messages(self, keyword):
        """
        模糊搜索协议名。返回匹配的 (消息名, 消息ID, 类型) 列表。
        """
        keyword = keyword.lower()
        results = []
        for enum_name, msg_id in MESSAGE_DEFINE.items():
            cs_name = f"CS{enum_name}"
            sc_name = f"SC{enum_name}"
            if keyword in enum_name.lower():
                has_cs = cs_name in self.cs_classes
                has_sc = sc_name in self.sc_classes
                types = []
                if has_cs:
                    types.append("CS")
                if has_sc:
                    types.append("SC")
                results.append((enum_name, msg_id, "/".join(types) if types else "?"))

        # 也搜索 CS/SC 前缀名
        for name, cls in sorted(self.cs_classes.items()):
            if keyword in name.lower():
                enum_name = name[2:]
                if enum_name not in MESSAGE_DEFINE:
                    results.append((name, "?", "CS"))

        for name, cls in sorted(self.sc_classes.items()):
            if keyword in name.lower():
                enum_name = name[2:]
                if enum_name not in MESSAGE_DEFINE:
                    results.append((name, "?", "SC"))

        return results

    def list_cs_messages(self):
        """列出所有可发送的 CS 消息"""
        result = []
        for name, cls in sorted(self.cs_classes.items()):
            msg_id = self.msg_name_to_id.get(name, "?")
            result.append((name, msg_id))
        return result
