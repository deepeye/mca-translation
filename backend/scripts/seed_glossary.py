"""批量导入系统术语库 — 从 JSON 导入中文术语 + 英文译法到 glossary_entries。

读取 [{source_term, preferred, alternatives}, ...] 格式的 JSON，为每个术语生成
DashScope 向量嵌入（text-embedding-v3, 1024 维），写入系统级术语库。
幂等：按 source_term 跳过已存在条目，中断后重跑安全。

Usage (在 backend 容器内, cwd=/app):
  python /tmp/seed_glossary.py /tmp/glossary_data.json
  python /tmp/seed_glossary.py /tmp/glossary_data.json --concurrency 8 --embed-batch 25
"""
import argparse
import asyncio
import json
import sys
import uuid
from collections import OrderedDict

import httpx
from sqlalchemy import select

from app.core.database import async_session
from app.llm.bailian import bailian_client
from app.models.glossary import GlossaryEntry

EN_CODE = "en-GB"  # 英语(英) — translations dict 的 key
TERM_TYPE = "political_discourse"  # 重要表述 → 政治话语


async def embed_with_retry(texts: list[str], retries: int = 4) -> list[list[float]]:
    """带重试的批量嵌入调用。DashScope 偶发 429/5xx 时指数退避。"""
    last_err = None
    for attempt in range(retries):
        try:
            return await bailian_client.embed(texts)
        except httpx.HTTPStatusError as e:
            last_err = e
            # 429 / 5xx 可重试
            if e.response.status_code not in (429, 500, 502, 503, 504):
                raise
            wait = 2 ** attempt
            print(f"  [embed] HTTP {e.response.status_code}, retry in {wait}s (attempt {attempt+1}/{retries})", flush=True)
            await asyncio.sleep(wait)
        except (httpx.RequestError, httpx.TransportError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  [embed] {type(e).__name__}, retry in {wait}s (attempt {attempt+1}/{retries})", flush=True)
            await asyncio.sleep(wait)
    raise RuntimeError(f"embed failed after {retries} retries: {last_err}")


async def embed_all(
    source_terms: list[str],
    embed_batch: int,
    concurrency: int,
) -> list[list[float] | None]:
    """并发批量生成嵌入，按输入顺序返回（None 表示该条失败）。"""
    sem = asyncio.Semaphore(concurrency)
    results: list[list[float] | None] = [None] * len(source_terms)

    async def run(start: int, batch: list[str]) -> None:
        async with sem:
            vecs = await embed_with_retry(batch)
            for i, v in enumerate(vecs):
                results[start + i] = v

    tasks = []
    for start in range(0, len(source_terms), embed_batch):
        batch = source_terms[start : start + embed_batch]
        tasks.append(run(start, batch))
    await asyncio.gather(*tasks)
    return results


def build_translations(preferred: str, alternatives: list[str]) -> dict:
    """构造 translations JSONB: {en-GB: {preferred, alternatives, notes}}。"""
    return {
        EN_CODE: {
            "preferred": preferred,
            "alternatives": alternatives or [],
            "notes": "",
        }
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入系统术语库。")
    parser.add_argument("input", help="JSON 文件路径")
    parser.add_argument("--embed-batch", type=int, default=25, help="单次嵌入 API 文本数 (default 25)")
    parser.add_argument("--concurrency", type=int, default=6, help="并发嵌入请求数 (default 6)")
    parser.add_argument("--insert-batch", type=int, default=200, help="单次 DB 提交条目数 (default 200)")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"Loaded {len(entries)} entries from {args.input}", flush=True)

    # 查询已存在 source_term → 幂等跳过
    async with async_session() as db:
        existing = {
            r[0]
            for r in (await db.execute(select(GlossaryEntry.source_term))).all()
        }
    print(f"Existing system glossary entries: {len(existing)}", flush=True)

    pending = [e for e in entries if e["source_term"] not in existing]
    skipped = len(entries) - len(pending)
    print(f"Pending: {len(pending)} | Skipped (existing): {skipped}", flush=True)
    if not pending:
        print("Nothing to import.", flush=True)
        return

    inserted = 0
    failed_embed = 0
    total = len(pending)
    for chunk_start in range(0, total, args.insert_batch):
        chunk = pending[chunk_start : chunk_start + args.insert_batch]
        terms = [e["source_term"] for e in chunk]
        embeddings = await embed_all(terms, args.embed_batch, args.concurrency)

        rows = []
        for e, emb in zip(chunk, embeddings):
            if emb is None:
                failed_embed += 1
                # 嵌入失败仍写入（embedding=NULL），保证术语可用；语义检索降级
                print(f"  [warn] no embedding for: {e['source_term'][:30]}", flush=True)
            rows.append(
                GlossaryEntry(
                    id=uuid.uuid4(),
                    source_term=e["source_term"],
                    term_type=TERM_TYPE,
                    translations=build_translations(e["preferred"], e.get("alternatives", [])),
                    risk_notes=None,
                    applicable_genres=None,
                    embedding=emb,
                )
            )

        async with async_session() as db:
            db.add_all(rows)
            await db.commit()
        inserted += len(rows)
        print(
            f"Inserted {inserted}/{total} "
            f"(chunk @ {chunk_start}, embed_fail={failed_embed})",
            flush=True,
        )

    print(
        f"\nDone. Inserted={inserted}, embed_failures={failed_embed}, "
        f"skipped_existing={skipped}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
