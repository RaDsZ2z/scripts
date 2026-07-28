#!/usr/bin/env python3
"""Batch image generation and editing with Micu's gpt-image-2 API."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import requests

from api_key_config import get_api_key


DEFAULT_BASE_URL = "https://www.micuapi.ai"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"


def image_extension(data: bytes, content_type: str = "") -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    return {"image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(
        content_type.split(";", 1)[0].lower(), "png"
    )


class MicuImageGenerator:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    def _decode_response(self, response: requests.Response) -> tuple[bytes, str]:
        if not response.ok:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text[:500]
            raise RuntimeError(f"API request failed ({response.status_code}): {detail}")
        try:
            body = response.json()
            item = body["data"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("API response does not contain image data") from exc

        if item.get("b64_json"):
            try:
                data = base64.b64decode(item["b64_json"], validate=True)
            except (ValueError, TypeError) as exc:
                raise RuntimeError("API returned invalid base64 image data") from exc
            return data, image_extension(data)

        url = item.get("url")
        if isinstance(url, str) and url.startswith("data:image/") and "," in url:
            header, encoded = url.split(",", 1)
            data = base64.b64decode(encoded)
            return data, image_extension(data, header[5:].split(";", 1)[0])
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            image_response = requests.get(url, timeout=120)
            image_response.raise_for_status()
            data = image_response.content
            return data, image_extension(data, image_response.headers.get("Content-Type", ""))
        raise RuntimeError("API response contains neither b64_json nor a usable image URL")

    def generate_image(
        self,
        prompt: str,
        output_dir: str | os.PathLike[str] = ".",
        image_path: str | list[str] | None = None,
        filename: str | None = None,
        model: str = DEFAULT_MODEL,
        size: str = DEFAULT_SIZE,
    ) -> tuple[bool, str, str | None]:
        output_path = Path(output_dir)
        name = filename or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = [image_path] if isinstance(image_path, str) else list(image_path or [])
        try:
            if paths:
                files: list[tuple[str, tuple[str, Any, str]]] = []
                handles = []
                try:
                    for value in paths:
                        path = Path(value)
                        if not path.is_file():
                            raise FileNotFoundError(f"Reference image does not exist: {path}")
                        handle = path.open("rb")
                        handles.append(handle)
                        mime = mimetypes.guess_type(path.name)[0] or "image/png"
                        files.append(("image[]", (path.name, handle, mime)))
                    response = requests.post(
                        f"{self.base_url}/v1/images/edits",
                        headers=self.headers,
                        data={"model": model, "prompt": prompt, "n": "1", "size": size, "response_format": "b64_json"},
                        files=files,
                        timeout=600,
                    )
                finally:
                    for handle in handles:
                        handle.close()
            else:
                response = requests.post(
                    f"{self.base_url}/v1/images/generations",
                    headers={**self.headers, "Content-Type": "application/json; charset=utf-8"},
                    json={"model": model, "prompt": prompt, "n": 1, "size": size, "response_format": "b64_json"},
                    timeout=600,
                )
            image_data, extension = self._decode_response(response)
            if len(image_data) < 100:
                raise RuntimeError("API returned an empty or invalid image")
            output_path.mkdir(parents=True, exist_ok=True)
            saved_path = output_path / f"{name}.{extension}"
            saved_path.write_bytes(image_data)
            return True, f"Image saved: {saved_path}", str(saved_path)
        except (OSError, requests.RequestException, RuntimeError, ValueError) as exc:
            return False, str(exc), None


def batch_generate(
    generator: MicuImageGenerator,
    tasks: list[dict[str, Any]],
    output_dir: str | os.PathLike[str],
    size: str = DEFAULT_SIZE,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, 1):
        prompt = str(task.get("prompt", "")).strip()
        if not prompt:
            results.append({"index": index, "success": False, "message": "Prompt is empty", "output_file": None})
            continue
        ok, message, saved_path = generator.generate_image(
            prompt,
            output_dir=output_dir,
            image_path=task.get("image_path") or None,
            filename=str(index),
            size=str(task.get("size") or size),
        )
        print(f"[{index}/{len(tasks)}] {'OK' if ok else 'FAILED'}: {message}")
        results.append({
            "index": index,
            "prompt": prompt,
            "image_path": task.get("image_path") or None,
            "success": ok,
            "message": message,
            "output_file": saved_path,
        })
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "batch_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Micu gpt-image-2 batch image generator")
    parser.add_argument("--tasks", default=str(Path(__file__).with_name("tasks.json")))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--size", default=DEFAULT_SIZE)
    args = parser.parse_args()

    api_key = get_api_key("MICU_API_KEY")
    if not api_key:
        raise SystemExit("MICU_API_KEY is not configured in api_keys.env")
    tasks_path = Path(args.tasks)
    try:
        tasks = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"Task file does not exist: {tasks_path}") from None
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit("Task file must contain a non-empty JSON array")
    output_dir = args.output_dir or str(
        Path(__file__).with_name("output") / dt.datetime.now().strftime("%m_%d_%H_%M_%S")
    )
    results = batch_generate(MicuImageGenerator(api_key), tasks, output_dir, args.size)
    if not all(item["success"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
