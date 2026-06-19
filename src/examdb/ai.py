from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

from .taxonomy import POLICY_TAGS, POLICY_TOPIC_KEYWORDS, TagSuggestion, suggest_policy_metadata


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat") -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str) -> dict:
        if not self.api_key:
            return {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


def suggest_policy_metadata_with_ai(
    title: str,
    content: str,
    client: DeepSeekClient | None = None,
    strict: bool = False,
) -> TagSuggestion:
    fallback = suggest_policy_metadata(title, content)
    client = client or DeepSeekClient()
    if not client.enabled:
        return fallback

    system = (
        "你是考公资料库的政策文章分类助手。"
        "只从给定标签中选择，不要创造新标签。"
        "输出 JSON，字段为 tags、topics、confidence。"
    )
    allowed_tags = sorted(POLICY_TAGS)
    allowed_topics = sorted(POLICY_TOPIC_KEYWORDS)
    excerpt = content[:3500]
    user = json.dumps(
        {
            "title": title,
            "excerpt": excerpt,
            "allowed_tags": allowed_tags,
            "allowed_topics": allowed_topics,
            "rules": [
                "tags 选择 1 到 3 个，必须代表文章主旨，不要因为顺带出现就打标签。",
                "topics 选择 0 到 4 个，用于就业、社保、乡村振兴等细分主题，或申论用途、规范表述。",
                "就业、社会保障、乡村振兴等细分词只能放入 topics，不能放入 tags。",
                "confidence 只能是 low、medium、high。",
            ],
        },
        ensure_ascii=False,
    )
    try:
        result = client.chat_json(system, user)
    except Exception:
        if strict:
            raise
        return fallback

    tags = _clean_labels(result.get("tags", []), allowed_tags, 3)
    topics = _clean_labels(result.get("topics", []), allowed_topics, 4)
    confidence = result.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        confidence = fallback.confidence
    if not tags:
        return fallback
    return TagSuggestion(tags=tags, topics=topics, confidence=confidence)


def _clean_labels(value: object, allowed: list[str], limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    allowed_set = set(allowed)
    for item in value:
        if not isinstance(item, str):
            continue
        label = item.strip()
        if label in allowed_set and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels
