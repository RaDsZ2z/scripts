#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPT-Image-2 (OpenAI) 图片生成 - Python版本
支持文生图和图生图，自动保存图片到本地
"""

import requests
import json
import base64
import os
import sys
import datetime
from typing import Optional, Tuple, List, Dict, Union

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


class GPTImageGenerator:
    def __init__(self, api_key: str, api_url: str = "https://api.laozhang.ai"):
        """
        初始化 GPT-Image 生成器

        Args:
            api_key: API密钥
            api_url: API基础地址（不含路径）
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def generate_image(self, prompt: str, model: str = "gpt-image-2",
                       output_dir: str = ".", image_path: Union[str, List[str], None] = None,
                       filename: Optional[str] = None,
                       size: str = "1024x1024") -> Tuple[bool, str, Optional[str]]:
        """
        生成图片并保存到本地

        Args:
            prompt: 图片描述提示词
            model: 使用的模型
            output_dir: 输出目录
            image_path: 参考图片路径（仅第一张会作为编辑输入）
            filename: 输出文件名（不含扩展名），默认用时间戳
            size: 图片尺寸，可选 1024x1024, 1536x1024, 1024x1536

        Returns:
            Tuple[是否成功, 结果消息, 实际保存路径]
        """
        print("🚀 开始生成图片...")
        print(f"提示词: {prompt}")
        print(f"模型: {model}")

        # 生成文件名
        name = filename or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"{name}.png")

        try:
            if image_path:
                # 有参考图 → 使用 /v1/images/edits
                ok, msg, saved_path = self._edit_image(prompt, model, image_path, output_file, size)
            else:
                # 纯文生图 → 使用 /v1/images/generations
                ok, msg, saved_path = self._generate(prompt, model, output_file, size)

            return ok, msg, saved_path

        except requests.exceptions.Timeout:
            return False, "请求超时（300秒）", None
        except requests.exceptions.ConnectionError as e:
            return False, f"连接错误: {str(e)}", None
        except Exception as e:
            return False, f"未知错误: {str(e)}", None

    def _generate(self, prompt: str, model: str, output_file: str,
                  size: str) -> Tuple[bool, str, Optional[str]]:
        """纯文生图 - POST /v1/images/generations"""
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }

        print("📡 发送生成请求...")

        response = requests.post(
            f"{self.api_url}/v1/images/generations",
            headers=self.headers,
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            error_msg = f"API请求失败，状态码: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f", 错误详情: {error_detail}"
            except Exception:
                error_msg += f", 响应内容: {response.text[:500]}"
            return False, error_msg, None

        print("✅ API请求成功，正在解析响应...")

        try:
            result = response.json()
        except json.JSONDecodeError as e:
            return False, f"JSON解析失败: {str(e)}", None

        return self._save_from_response(result, output_file)

    def _edit_image(self, prompt: str, model: str,
                    image_path: Union[str, List[str], None],
                    output_file: str, size: str) -> Tuple[bool, str, Optional[str]]:
        """图生图 - POST /v1/images/edits"""
        # 取第一张图作为编辑输入
        paths = [image_path] if isinstance(image_path, str) else image_path
        ref_path = paths[0]

        if not os.path.isfile(ref_path):
            return False, f"参考图片不存在: {ref_path}", None

        print(f"📎 参考图片: {ref_path}")

        # 如果有多张参考图，将提示词中追加说明
        effective_prompt = prompt
        if len(paths) > 1:
            extra = []
            for i, p in enumerate(paths[1:], 2):
                if os.path.isfile(p):
                    print(f"📎 附加参考图: {p}")
                    extra.append(f"(参考图{i}: {p})")
            if extra:
                effective_prompt = prompt + "\n" + "\n".join(extra)

        print("📡 发送编辑请求...")

        # multipart/form-data
        files = {
            "image": ("image.png", open(ref_path, "rb"), "image/png"),
        }
        form_data = {
            "model": model,
            "prompt": effective_prompt,
            "n": "1",
            "size": size,
        }
        # 不能用 self.headers 中的 Content-Type，requests 会自动设置 multipart boundary
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.post(
            f"{self.api_url}/v1/images/edits",
            headers=headers,
            data=form_data,
            files=files,
            timeout=300
        )

        if response.status_code != 200:
            error_msg = f"API请求失败，状态码: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f", 错误详情: {error_detail}"
            except Exception:
                error_msg += f", 响应内容: {response.text[:500]}"
            return False, error_msg, None

        print("✅ API请求成功，正在解析响应...")

        try:
            result = response.json()
        except json.JSONDecodeError as e:
            return False, f"JSON解析失败: {str(e)}", None

        return self._save_from_response(result, output_file)

    def _save_from_response(self, result: dict, output_file: str) -> Tuple[bool, str, Optional[str]]:
        """从 API 响应中保存图片（支持 b64_json 和 url 两种格式）"""
        data_list = result.get("data", [])
        if not data_list:
            return False, "响应中未包含图片数据", None

        item = data_list[0]

        # 优先 b64_json
        if "b64_json" in item:
            b64_data = item["b64_json"]
            print(f"📏 Base64数据长度: {len(b64_data)} 字符")
            image_data = base64.b64decode(b64_data)

            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            with open(output_file, 'wb') as f:
                f.write(image_data)

            print(f'🖼️  图片保存成功: {output_file}')
            print(f'📊 文件大小: {len(image_data)} 字节')
            return True, f"图片保存成功: {output_file}", output_file

        # 备选 url
        if "url" in item:
            url = item["url"]
            print(f"🔗 从URL下载图片: {url[:100]}...")
            img_resp = requests.get(url, timeout=120)
            if img_resp.status_code != 200:
                return False, f"下载图片失败，状态码: {img_resp.status_code}", None

            image_data = img_resp.content
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            with open(output_file, 'wb') as f:
                f.write(image_data)

            print(f'🖼️  图片保存成功: {output_file}')
            print(f'📊 文件大小: {len(image_data)} 字节')
            return True, f"图片保存成功: {output_file}", output_file

        return False, "响应中未包含可识别的图片数据（b64_json/url）", None


def batch_generate(generator: GPTImageGenerator, tasks: List[Dict], output_dir: str = "output",
                   script_dir: str = ".", interval: int = 5, max_retries: int = 5):
    """
    批量生成图片

    Args:
        generator: 生成器实例
        tasks: 任务列表，每项包含 prompt 和可选的 image_path
        output_dir: 输出目录
        script_dir: 脚本所在目录（用于生成 tasks_next.json 的相对路径）
    """
    os.makedirs(output_dir, exist_ok=True)
    total = len(tasks)
    success_count = 0
    fail_count = 0
    results = []

    # 预检查所有参考图片路径
    print("🔍 检查参考图片路径...")
    errors = []
    for i, task in enumerate(tasks, 1):
        image_path = task.get("image_path") or None
        if not image_path:
            continue
        paths = [image_path] if isinstance(image_path, str) else image_path
        for p in paths:
            if not os.path.isfile(p):
                errors.append(f"  任务 {i}: 图片不存在 → {p}")
    if errors:
        print(f"\n❌ 发现 {len(errors)} 个图片路径错误:\n")
        for e in errors:
            print(e)
        print(f"\n请修改 tasks.json 后重新运行。")
        return

    print("✅ 所有参考图片路径正确\n")
    print(f"📋 共 {total} 个任务，开始批量处理...\n")

    for i, task in enumerate(tasks, 1):
        prompt = task.get("prompt", "")
        image_path = task.get("image_path") or None

        print(f"{'='*60}")
        print(f"[{i}/{total}] 处理中...")
        print(f"提示词: {prompt}")
        if image_path:
            print(f"参考图: {image_path}")
        print(f"{'='*60}")

        ok, msg, saved_path = False, "", None
        for attempt in range(1, max_retries + 1):
            ok, msg, saved_path = generator.generate_image(prompt, image_path=image_path, output_dir=output_dir, filename=str(i))
            if ok:
                break
            if attempt < max_retries:
                print(f"🔄 第 {attempt} 次尝试失败，等待 {interval} 秒后重试...")
                import time
                time.sleep(interval)

        if ok:
            success_count += 1
            print(f"✅ [{i}/{total}] {msg}")
        else:
            fail_count += 1
            print(f"❌ [{i}/{total}] {max_retries} 次尝试均失败: {msg}")

        results.append({"index": i, "prompt": prompt, "image_path": image_path,
                         "success": ok, "message": msg, "output_file": saved_path})

        # 任务间隔，避免请求过快
        if i < total:
            print(f"⏳ 等待 {interval} 秒后继续...\n")
            import time
            time.sleep(interval)
        print()

    # 汇总
    print(f"\n{'='*60}")
    print(f"📊 批量处理完成: 成功 {success_count}, 失败 {fail_count}, 共 {total}")
    print(f"{'='*60}")

    # 保存结果到 JSON
    result_file = os.path.join(output_dir, "batch_results.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"📄 结果已保存到: {result_file}")

    # 生成下一轮任务模板
    next_tasks = []
    for r in results:
        if r["output_file"]:
            rel_path = os.path.relpath(r["output_file"], script_dir).replace("\\", "/")
        else:
            rel_path = None
        next_tasks.append({"prompt": "", "image_path": rel_path})

    next_file = os.path.join(script_dir, "tasks_next.json")
    with open(next_file, "w", encoding="utf-8") as f:
        json.dump(next_tasks, f, ensure_ascii=False, indent=2)
    print(f"📝 已生成 tasks_next.json，编辑后重命名为 tasks.json 即可运行下一轮")


def main():
    # ===== 固定配置，一般不需要修改 =====
    API_KEY = "API_KEY"
    OUTPUT_DIR = "output"
    # ====================================

    # 脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, "tasks.json")
    run_folder = datetime.datetime.now().strftime("%m_%d_%H_%M_%S")
    output_dir = os.path.join(script_dir, OUTPUT_DIR, run_folder)

    print("=" * 60)
    print("  GPT-Image-2 (OpenAI) 图片生成器")
    print("=" * 60)
    print(f"  开始时间: {datetime.datetime.now()}\n")

    # 读取 tasks.json
    if not os.path.isfile(json_file):
        print(f"❌ 找不到任务文件: {json_file}")
        print("   请在脚本同目录下创建 tasks.json 文件")
        input("\n按回车键退出...")
        sys.exit(1)

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ tasks.json 格式有误: {e}")
        input("\n按回车键退出...")
        sys.exit(1)

    if not isinstance(tasks, list) or len(tasks) == 0:
        print("❌ tasks.json 应为非空数组，请检查内容")
        input("\n按回车键退出...")
        sys.exit(1)

    print(f"📄 已读取任务文件，共 {len(tasks)} 个任务\n")

    generator = GPTImageGenerator(API_KEY)
    batch_generate(generator, tasks, output_dir=output_dir, script_dir=script_dir)

    print(f"\n  结束时间: {datetime.datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
