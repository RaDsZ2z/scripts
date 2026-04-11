#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nano Banana (Gemini) 图片生成 - Python版本
支持非流式输出和自动保存base64图片到本地
"""

import requests
import json
import base64
import re
import os
import sys
import datetime
from typing import Optional, Tuple, List, Dict, Union

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

class GeminiImageGenerator:
    def __init__(self, api_key: str, api_url: str = "https://api.laozhang.ai/v1/chat/completions"):
        """
        初始化Gemini图片生成器
        
        Args:
            api_key: API密钥（按次计费类型）
            api_url: API地址
        """
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def generate_image(self, prompt: str, model: str = "gemini-3.1-flash-image-preview",
                      output_dir: str = ".", image_path: Union[str, List[str], None] = None,
                      filename: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        生成图片并保存到本地

        Args:
            prompt: 图片描述提示词
            model: 使用的模型
            output_dir: 输出目录
            image_path: 参考图片路径，支持单个路径或路径列表
            filename: 输出文件名（不含扩展名），默认用时间戳

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
            # 构建 content
            content_parts = [{"type": "text", "text": prompt}]

            if image_path:
                # 统一转为列表
                paths = [image_path] if isinstance(image_path, str) else image_path
                for p in paths:
                    if not os.path.isfile(p):
                        return False, f"参考图片不存在: {p}", None
                    ext = os.path.splitext(p)[1].lower().lstrip('.')
                    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
                    mime = f"image/{mime_map.get(ext, 'png')}"
                    with open(p, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}
                    })
                    print(f"📎 已附带参考图片: {p}")

            # 准备请求数据
            payload = {
                "model": model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": content_parts
                    }
                ]
            }
            
            print("📡 发送API请求...")
            
            # 发送非流式请求
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=300
            )
            
            if response.status_code != 200:
                error_msg = f"API请求失败，状态码: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f", 错误详情: {error_detail}"
                except:
                    error_msg += f", 响应内容: {response.text[:500]}"
                return False, error_msg, None
            
            print("✅ API请求成功，正在解析响应...")
            
            # 解析JSON响应
            try:
                result = response.json()
                print("✅ 成功解析JSON响应")
            except json.JSONDecodeError as e:
                return False, f"JSON解析失败: {str(e)}", None
            
            # 提取消息内容
            full_content = ""
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    full_content = choice["message"]["content"]
            
            if not full_content:
                return False, "未找到消息内容", None
            
            print(f"📝 获取到消息内容，长度: {len(full_content)} 字符")
            print("🔍 正在解析图片数据...")
            
            # 提取并保存图片
            success, message, saved_path = self._extract_and_save_images(full_content, output_file)

            # 将文字部分保存到 txt 文件（去掉 base64 图片数据）
            text_only = re.sub(r'!\[image\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)', '', full_content).strip()
            txt_dir = os.path.join(os.path.dirname(output_file), "txt")
            os.makedirs(txt_dir, exist_ok=True)
            txt_file = os.path.join(txt_dir, os.path.basename(output_file).rsplit('.', 1)[0] + '.txt')
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(text_only)
            print(f"📝 响应文字已保存到: {txt_file}")

            if success:
                return True, message, saved_path
            else:
                print(f"💬 模型返回了文字而非图片")
                print(f"📄 文字内容: {full_content[:300]}")
                return False, f"模型未返回图片（文字已保存到 {txt_file}）", None

        except requests.exceptions.Timeout:
            return False, "请求超时（300秒）", None
        except requests.exceptions.ConnectionError as e:
            return False, f"连接错误: {str(e)}", None
        except Exception as e:
            return False, f"未知错误: {str(e)}", None
    
    def _extract_and_save_images(self, content: str, base_output_file: str) -> Tuple[bool, str, Optional[str]]:
        """
        高效提取并保存base64图片数据

        Args:
            content: 包含图片数据的内容
            base_output_file: 基础输出文件路径

        Returns:
            Tuple[是否成功, 结果消息, 实际保存路径]
        """
        try:
            print(f"📄 内容预览（前200字符）: {content[:200]}")

            # 使用精确的正则表达式提取base64图片数据
            base64_pattern = r'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)'
            match = re.search(base64_pattern, content)

            if not match:
                print('⚠️  未找到base64图片数据')
                return False, "响应中未包含base64图片数据", None

            image_format = match.group(1)  # png, jpg, etc.
            b64_data = match.group(2)

            print(f'🎨 图像格式: {image_format}')
            print(f'📏 Base64数据长度: {len(b64_data)} 字符')

            # 解码并保存图片
            image_data = base64.b64decode(b64_data)

            if len(image_data) < 100:
                return False, "解码后的图片数据太小，可能无效", None

            # 根据检测到的格式设置文件扩展名
            output_file = base_output_file.replace('.png', f'.{image_format}')
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)

            with open(output_file, 'wb') as f:
                f.write(image_data)

            print(f'🖼️  图片保存成功: {output_file}')
            print(f'📊 文件大小: {len(image_data)} 字节')

            return True, f"图片保存成功: {output_file}", output_file

        except Exception as e:
            return False, f"处理图片时发生错误: {str(e)}", None

def batch_generate(generator: GeminiImageGenerator, tasks: List[Dict], output_dir: str = "output",
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
    print("  Nano Banana (Gemini) 图片生成器")
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

    generator = GeminiImageGenerator(API_KEY)
    batch_generate(generator, tasks, output_dir=output_dir, script_dir=script_dir)

    print(f"\n  结束时间: {datetime.datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    main()