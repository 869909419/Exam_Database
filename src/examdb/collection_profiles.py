from __future__ import annotations


COLLECTION_PROFILES: dict[str, tuple[str, ...]] = {
    "politics-theory": (
        "中国式现代化",
        "进一步全面深化改革",
        "二十届三中全会",
        "二十届四中全会",
        "十五五",
        "新质生产力",
        "高质量发展",
        "科技强国",
        "科技自立自强",
        "教育强国",
        "就业优先",
        "高质量充分就业",
        "人口高质量发展",
        "中华民族共同体",
        "民族团结进步",
        "党的自我革命",
        "全面从严治党",
        "国家安全",
        "数字政府",
        "数字贸易",
        "质量强国",
        "共同富裕",
        "法治",
        "绿色低碳",
        "城乡融合",
        "现代化产业体系",
        "文化强国",
        "国际传播",
        "全球治理",
    )
}


def keywords_for_profile(profile: str | None) -> list[str]:
    if not profile:
        return []
    if profile not in COLLECTION_PROFILES:
        known = ", ".join(sorted(COLLECTION_PROFILES))
        raise ValueError(f"Unsupported collection profile '{profile}'. Available: {known}")
    return list(COLLECTION_PROFILES[profile])


def parse_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def article_matches_keywords(title: str, content: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{title}\n{content}"
    return any(keyword in haystack for keyword in keywords)
