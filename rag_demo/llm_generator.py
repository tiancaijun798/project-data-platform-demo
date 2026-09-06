#!/usr/bin/env python3
"""
LLM Generator — OpenAI-compatible API 调用封装。

支持 DeepSeek、OpenAI、或其他兼容 API 的 Chat Completions 端点。
通过环境变量配置:
    LLM_API_KEY      — API 密钥
    LLM_API_BASE_URL — API Base URL (默认: https://api.deepseek.com/v1)
    LLM_MODEL        — 模型名 (默认: deepseek-chat)

用法:
    from llm_generator import LLMGenerator
    gen = LLMGenerator()
    answer = gen.generate(query="...", context_docs=[...])
"""

import json
import os
import sys
import time
from typing import Optional

import requests


# ---- 配置 ----
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_BASE_URL = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))


class LLMGenerator:
    """OpenAI-compatible Chat Completions API 封装。

    支持多种 provider:
        - DeepSeek:   base_url=https://api.deepseek.com/v1, model=deepseek-chat
        - OpenAI:     base_url=https://api.openai.com/v1, model=gpt-4o-mini
        - 其他兼容:   设置 LLM_API_BASE_URL 和 LLM_MODEL 即可
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature

        if not self.api_key:
            print("  [WARN] LLM_API_KEY not set - generation unavailable")
            print("  [INFO] Set LLM_API_KEY in .env file")

    def _build_system_prompt(self, context_docs: list[dict]) -> str:
        """从检索文档构建系统提示。"""
        doc_type = context_docs[0].get("event_type", "event") if context_docs else "event"
        return (
            f"You are a data analytics assistant. "
            f"Use the retrieved user {doc_type} data below to answer the user's question. "
            f"If the data does not contain enough information, say so clearly. "
            f"Provide specific user IDs, event types, counts, and patterns where possible. "
            f"Respond in the same language as the user's question."
        )

    def _build_context(self, docs: list[dict]) -> str:
        """将检索到的文档组装为上下文。"""
        entries = []
        for i, doc in enumerate(docs, 1):
            entry = (
                f"{i}. [Event: {doc.get('event_type', '?')} | "
                f"User: {doc.get('user_id', '?')} | "
                f"Product: {doc.get('product_id') or 'N/A'} | "
                f"Score: {doc.get('score', 0):.3f}]\n"
                f"   {doc.get('chunk', '')}"
            )
            entries.append(entry)
        return "\n".join(entries)

    def _build_generation_prompt(self, query: str, docs: list[dict]) -> str:
        """构建完整的生成提示（已整合 system + context + query）。"""
        system = self._build_system_prompt(docs)
        context = self._build_context(docs)

        return f"""{system}

## Context (retrieved from data platform knowledge base)
{context}

## User Question
{query}

## Answer
"""

    def generate(
        self,
        query: str,
        context_docs: list[dict],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """调用 LLM 生成答案。

        Args:
            query: 用户问题
            context_docs: 检索到的文档列表 (来自 FAISS/Milvus)
            system_prompt: 自定义系统提示（覆盖默认）
            max_tokens: 最大生成 token 数
            temperature: 生成温度

        Returns:
            {
                "answer": str,            # LLM 生成的答案
                "model": str,             # 使用的模型
                "usage": dict,            # token 使用统计
                "elapsed_ms": float,      # API 调用耗时
                "error": str | None,      # 错误信息（如果有）
            }
        """
        if not self.api_key:
            return {
                "answer": "",
                "model": self.model,
                "usage": {},
                "elapsed_ms": 0,
                "error": "LLM_API_KEY not configured. Set it in .env file.",
            }

        if not context_docs:
            return {
                "answer": "",
                "model": self.model,
                "usage": {},
                "elapsed_ms": 0,
                "error": "No context documents provided for generation.",
            }

        # 构建消息
        user_prompt = query
        if context_docs:
            context_block = self._build_context(context_docs)
            user_prompt = (
                f"## Context (retrieved from data platform)\n{context_block}\n\n"
                f"## User Question\n{query}"
            )

        sys_prompt = system_prompt or self._build_system_prompt(context_docs)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 调用 API
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "stream": False,
        }

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            elapsed_ms = round((time.time() - t0) * 1000, 1)

            if resp.status_code != 200:
                return {
                    "answer": "",
                    "model": self.model,
                    "usage": {},
                    "elapsed_ms": elapsed_ms,
                    "error": f"API error {resp.status_code}: {resp.text[:200]}",
                }

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            answer = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return {
                "answer": answer.strip(),
                "model": data.get("model", self.model),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "elapsed_ms": elapsed_ms,
                "error": None,
            }

        except requests.exceptions.Timeout:
            return {
                "answer": "",
                "model": self.model,
                "usage": {},
                "elapsed_ms": (time.time() - t0) * 1000,
                "error": "API request timed out (60s)",
            }
        except Exception as e:
            return {
                "answer": "",
                "model": self.model,
                "usage": {},
                "elapsed_ms": (time.time() - t0) * 1000,
                "error": str(e),
            }

    def is_available(self) -> bool:
        """检查 LLM 是否可用。"""
        return bool(self.api_key)


# ---- 命令行测试 ----
if __name__ == "__main__":
    # 快速测试 LLM 连接
    gen = LLMGenerator()

    if not gen.is_available():
        print("[ERROR] LLM not available: set LLM_API_KEY env var")
        print("[INFO] Add to .env: LLM_API_KEY=your-key")
        sys.exit(1)

    print(f"[TEST] LLM Generator")
    print(f"   Base URL: {gen.base_url}")
    print(f"   Model: {gen.model}")

    # 模拟上下文
    mock_docs = [
        {
            "chunk": "User U0001 performed purchase on product P0100 via mobile Chrome from google on page checkout",
            "event_type": "purchase",
            "user_id": "U0001",
            "product_id": "P0100",
            "score": 0.95,
        },
        {
            "chunk": "User U0002 performed add_to_cart on product P0200 via desktop Firefox from direct",
            "event_type": "add_to_cart",
            "user_id": "U0002",
            "product_id": "P0200",
            "score": 0.82,
        },
    ]

    result = gen.generate(
        query="哪些用户通过移动端完成了购买？",
        context_docs=mock_docs,
    )

    if result["error"]:
        print(f"[ERROR] Generation failed: {result['error']}")
    else:
        print(f"[OK] Generation success ({result['elapsed_ms']}ms)")
        print(f"   Model: {result['model']}")
        print(f"   Tokens: {result['usage']}")
        print(f"\nAnswer:\n{result['answer']}")
