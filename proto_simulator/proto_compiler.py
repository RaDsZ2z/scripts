# -*- coding: utf-8 -*-
"""
将 .proto 编译为 Python protobuf 类。

优先使用 grpcio-tools 提供的现代 protoc（与新版 protobuf 库兼容），
回退到项目自带的 protoc.exe。

编译后自动修补 import 路径，使生成的 _pb2 模块在 _generated/ 包内可正常互相引用。
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from .config import PROTO_DIR, PROTOC_EXE, GENERATED_DIR


def compile_protos(force=False):
    """
    编译所有 .proto 文件为 Python protobuf 代码。

    :param force: 即使已生成也强制重新编译
    :return: True 成功, False 失败
    """
    if not PROTO_DIR.exists():
        print(f"[错误] Proto 目录不存在: {PROTO_DIR}")
        return False

    proto_files = sorted(PROTO_DIR.glob("*.proto"))
    if not proto_files:
        print(f"[错误] 未找到 .proto 文件: {PROTO_DIR}")
        return False

    # 检查是否需要编译
    generated_files = list(GENERATED_DIR.glob("*_pb2.py")) if GENERATED_DIR.exists() else []
    if not force and generated_files:
        expected_count = len(proto_files)
        if len(generated_files) >= expected_count:
            print(f"[跳过] 已有 {len(generated_files)} 个生成文件，使用 --compile 强制重新编译")
            return True

    # 确保输出目录存在
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[编译] 共 {len(proto_files)} 个 .proto 文件 ...")

    # 尝试使用 grpcio-tools 的 protoc
    success = _compile_with_grpc_tools(proto_files)

    if not success:
        # 回退到项目自带的 protoc.exe
        success = _compile_with_protoc(proto_files)

    if not success:
        return False

    # 修补 import
    _patch_imports()

    generated = list(GENERATED_DIR.glob("*_pb2.py"))
    print(f"[完成] 生成 {len(generated)} 个 _pb2.py 文件 → {GENERATED_DIR}")
    return True


def _compile_with_grpc_tools(proto_files):
    """使用 grpcio-tools 的 protoc 编译（推荐，与新版 protobuf 兼容）"""
    try:
        from grpc_tools import protoc
    except ImportError:
        print("[提示] grpcio-tools 未安装，尝试使用项目自带 protoc")
        return False

    import os
    out_dir_str = str(GENERATED_DIR)

    # grpc_tools.protoc 要求 proto 文件路径匹配 --proto_path 前缀
    # 切换到 proto 目录执行可避免路径问题
    saved_cwd = os.getcwd()
    proto_dir_str = str(PROTO_DIR)
    try:
        os.chdir(proto_dir_str)
        # 一次性编译所有文件
        args = [
            f"--proto_path=.",
            f"--python_out={out_dir_str}",
        ] + [f.name for f in proto_files]

        result = protoc.main(args)
        if result != 0:
            print(f"[警告] grpc_tools.protoc 返回 {result}")
            return False
    except Exception as e:
        print(f"[警告] grpc_tools.protoc 编译失败: {e}")
        return False
    finally:
        os.chdir(saved_cwd)

    print("[编译] 使用 grpcio-tools (现代 protoc)")
    return True


def _compile_with_protoc(proto_files):
    """使用项目自带的 protoc.exe 编译"""
    if not PROTOC_EXE.exists():
        print(f"[错误] 找不到 protoc: {PROTOC_EXE}")
        print("  提示: 安装 grpcio-tools (pip install grpcio-tools) 或检查路径")
        return False

    cmd = [
        str(PROTOC_EXE),
        f"--python_out={GENERATED_DIR}",
        f"--proto_path={PROTO_DIR}",
    ] + [str(p) for p in proto_files]

    print(f"[编译] 使用项目自带 protoc: {PROTOC_EXE.name}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError:
        print(f"[错误] 无法执行 protoc: {PROTOC_EXE}")
        return False
    except subprocess.TimeoutExpired:
        print("[错误] protoc 编译超时")
        return False

    if result.returncode != 0:
        print(f"[错误] protoc 返回码 {result.returncode}")
        if result.stderr:
            print(result.stderr)
        return False

    if result.stderr:
        for line in result.stderr.strip().split("\n"):
            if line.strip():
                print(f"  [警告] {line}")

    return True


def _patch_imports():
    """
    修补生成文件中的 import 语句。

    protoc 生成的代码形如: import xxx_pb2
    需改为相对导入: from . import xxx_pb2
    """
    if not GENERATED_DIR.exists():
        return

    import_pattern = re.compile(r'^import (\w+_pb2)', re.MULTILINE)
    replacement = r'from . import \1'

    for pb2_file in GENERATED_DIR.glob("*_pb2.py"):
        content = pb2_file.read_text(encoding="utf-8")
        new_content = import_pattern.sub(replacement, content)
        if new_content != content:
            pb2_file.write_text(new_content, encoding="utf-8")

    # 更新 __init__.py
    _update_init()


def _update_init():
    """更新 _generated/__init__.py，导入所有 _pb2 模块。"""
    if not GENERATED_DIR.exists():
        return

    pb2_modules = sorted(p.stem for p in GENERATED_DIR.glob("*_pb2.py"))
    lines = ["# -*- coding: utf-8 -*-", ""]

    for mod in pb2_modules:
        lines.append(f"from . import {mod}")

    init_file = GENERATED_DIR / "__init__.py"
    init_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_generated():
    """
    确保生成的代码可用。如果尚未编译则自动编译。
    """
    generated_files = list(GENERATED_DIR.glob("*_pb2.py")) if GENERATED_DIR.exists() else []
    if not generated_files:
        print("[自动编译] 首次运行，正在编译 proto 文件 ...")
        return compile_protos(force=False)
    return True
