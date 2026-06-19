from __future__ import annotations

from dataclasses import dataclass


POLICY_TAGS = {
    "时政热点",
    "党建",
    "经济",
    "法治",
    "民生",
    "生态",
    "基层治理",
    "科技教育人才",
    "文化建设",
    "国际观察",
}

POLICY_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "党建": ("党建", "全面从严治党", "管党治党", "兴党强党", "党员", "党组织", "习近平党建思想"),
    "经济": ("经济", "高质量发展", "产业", "消费", "投资", "市场", "金融", "新质生产力"),
    "法治": ("法治", "法律", "司法", "依法", "法治保障", "习近平法治思想"),
    "民生": ("民生", "就业", "医疗", "养老", "住房", "社会保障", "生活性服务业"),
    "生态": ("生态", "绿色", "环境", "双碳", "污染", "美丽中国"),
    "基层治理": ("基层", "社区", "乡村", "治理", "网格", "群众路线"),
    "科技教育人才": ("教育", "科技", "人才", "高校", "研究型大学", "创新创造"),
    "文化建设": ("文化", "文明", "文艺", "中华文明", "文化中国"),
    "国际观察": ("欧洲", "国际", "全球", "世界", "外交"),
    "时政热点": ("中国式现代化", "改革", "开放", "安全", "十五五", "现代化国家"),
}

POLICY_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "申论素材": ("问题", "对策", "成效", "经验", "启示", "路径", "要求"),
    "规范表述": ("坚持", "完善", "健全", "推动", "必须", "着力", "加快"),
    "就业": ("就业", "高校毕业生", "择业", "创业", "灵活就业", "劳动者"),
    "社会保障": ("社保", "社会保障", "养老", "医保", "救助", "福利"),
    "乡村振兴": ("乡村振兴", "农业农村", "三农", "高标准农田", "粮食安全"),
    "应急管理": ("应急", "突发事件", "防灾", "减灾", "安全生产", "风险防范"),
    "营商环境": ("营商环境", "政务服务", "监管", "企业", "市场主体"),
    "科技创新": ("科技创新", "基础研究", "人工智能", "数据", "算力", "知识产权"),
    "人才培养": ("人才培养", "教育科技人才", "高校", "职业教育", "创新人才"),
    "文化传承": ("文化遗产", "中华文明", "文脉", "文艺", "文化创新"),
    "基层减负": ("基层减负", "形式主义", "为基层减负", "基层负担"),
    "公共服务": ("公共服务", "医疗", "养老", "教育", "住房", "服务业"),
}

QUESTION_TYPES = {
    "言语理解",
    "数量关系",
    "判断推理",
    "资料分析",
    "常识判断",
    "归纳概括",
    "综合分析",
    "提出对策",
    "贯彻执行",
    "文章写作",
    "职业能力倾向测验",
    "综合应用能力",
    "公共基础知识",
}

PAPER_KINDS = {
    "行测",
    "申论",
    "职测",
    "综应",
    "公基",
}

EXAM_CATEGORIES = {
    "公务员",
    "事业编",
}

QUESTION_FORMATS = {
    "单选",
    "多选",
    "判断",
    "不定项",
    "材料分析",
    "写作",
    "客观题",
    "主观题",
}

PUBLIC_BASE_KNOWLEDGE_POINTS = {
    "政治",
    "法律",
    "经济",
    "公文",
    "管理",
    "人文科技",
    "省情市情",
}


@dataclass(frozen=True)
class TagSuggestion:
    tags: list[str]
    topics: list[str]
    confidence: str


def suggest_policy_metadata(title: str, text: str, tag_limit: int = 3) -> TagSuggestion:
    tag_scores = _score_keywords(title, text, POLICY_TAG_KEYWORDS)
    strong_tags = _select_strong_labels(tag_scores, tag_limit)
    topic_scores = _score_keywords(title, text, POLICY_TOPIC_KEYWORDS)
    topics = [label for label, score in topic_scores if score >= 2][:4]

    if strong_tags:
        confidence = "medium" if len(strong_tags) == 1 else "high"
    else:
        confidence = "low"
        strong_tags = ["待复核"]
    return TagSuggestion(tags=strong_tags, topics=topics, confidence=confidence)


def suggest_policy_tags(text: str, limit: int = 3) -> list[str]:
    return suggest_policy_metadata("", text, tag_limit=limit).tags


def validate_question_type(question_type: str | None) -> str | None:
    if not question_type:
        return None
    if question_type not in QUESTION_TYPES:
        raise ValueError(f"Unsupported question_type: {question_type}")
    return question_type


def validate_paper_kind(paper_kind: str | None) -> str | None:
    if not paper_kind:
        return None
    if paper_kind not in PAPER_KINDS:
        raise ValueError(f"Unsupported paper_kind: {paper_kind}")
    return paper_kind


def suggest_question_metadata(stem: str, options: dict[str, str] | None = None, paper_kind: str | None = None) -> TagSuggestion:
    text = stem or ""
    option_count = len(options or {})
    question_type: str | None = None
    topics: list[str] = []

    if paper_kind == "申论":
        question_type = _suggest_shenlun_type(text)
    elif paper_kind == "综应":
        question_type = "综合应用能力"
    elif paper_kind == "公基":
        question_type = "公共基础知识"
        topics = _suggest_public_base_points(text)
    elif paper_kind == "职测":
        question_type = _suggest_xingce_type(text)
        if question_type is None:
            question_type = "职业能力倾向测验"
    else:
        question_type = _suggest_xingce_type(text)

    if question_type is None:
        question_type = "常识判断" if option_count else "综合分析"
        confidence = "low"
    else:
        confidence = "medium"
    return TagSuggestion(tags=[question_type], topics=topics, confidence=confidence)


def suggest_question_format(stem: str, options: dict[str, str] | None = None, paper_kind: str | None = None) -> str:
    text = stem or ""
    option_count = len(options or {})
    if "判断" in text and option_count <= 2:
        return "判断"
    if any(keyword in text for keyword in ("多选", "多项", "不止一项")):
        return "多选"
    if "不定项" in text:
        return "不定项"
    if paper_kind in {"申论", "综应"}:
        if any(keyword in text for keyword in ("作文", "文章", "议论文", "参考给定资料")):
            return "写作"
        return "主观题"
    if option_count:
        return "单选"
    return "材料分析"


def _suggest_xingce_type(text: str) -> str | None:
    if any(keyword in text for keyword in ("资料", "图表", "增长率", "比重", "同比", "环比", "百分点", "表中")):
        return "资料分析"
    if any(keyword in text for keyword in ("逻辑", "推理", "定义判断", "类比", "图形", "论证", "削弱", "加强")):
        return "判断推理"
    if any(keyword in text for keyword in ("言语", "填入", "语句", "主旨", "意在", "排序", "病句")):
        return "言语理解"
    if any(keyword in text for keyword in ("计算", "工程", "行程", "利润", "概率", "排列", "组合", "方程")):
        return "数量关系"
    if any(keyword in text for keyword in ("法律", "宪法", "行政", "时政", "历史", "地理", "科技", "公文")):
        return "常识判断"
    return None


def _suggest_shenlun_type(text: str) -> str:
    if any(keyword in text for keyword in ("概括", "归纳", "总结")):
        return "归纳概括"
    if any(keyword in text for keyword in ("分析", "理解", "评价", "认识")):
        return "综合分析"
    if any(keyword in text for keyword in ("对策", "建议", "措施", "解决")):
        return "提出对策"
    if any(keyword in text for keyword in ("倡议书", "讲话稿", "简报", "通知", "宣传稿", "提纲")):
        return "贯彻执行"
    if any(keyword in text for keyword in ("文章", "作文", "议论文")):
        return "文章写作"
    return "综合分析"


def _suggest_public_base_points(text: str) -> list[str]:
    mapping = {
        "政治": ("马克思", "习近平", "党", "政治", "哲学", "中国特色社会主义"),
        "法律": ("法律", "宪法", "民法", "刑法", "行政法", "诉讼"),
        "经济": ("经济", "市场", "财政", "货币", "供给", "需求"),
        "公文": ("公文", "通知", "报告", "请示", "函", "纪要"),
        "管理": ("管理", "组织", "决策", "领导", "公共管理"),
        "人文科技": ("历史", "文学", "文化", "科技", "物理", "化学", "生物"),
        "省情市情": ("四川", "重庆", "本省", "本市", "省情", "市情"),
    }
    points = [label for label, keywords in mapping.items() if any(keyword in text for keyword in keywords)]
    return points[:3]


def _score_keywords(title: str, text: str, keywords_by_label: dict[str, tuple[str, ...]]) -> list[tuple[str, int]]:
    scores: list[tuple[str, int]] = []
    title_text = title or ""
    body_text = text or ""
    for label, keywords in keywords_by_label.items():
        score = 0
        for keyword in keywords:
            score += title_text.count(keyword) * 5
            score += body_text.count(keyword)
        if score:
            scores.append((label, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def _select_strong_labels(scores: list[tuple[str, int]], limit: int) -> list[str]:
    if not scores:
        return []
    top_score = scores[0][1]
    selected: list[str] = []
    for label, score in scores:
        if score < 3:
            continue
        if score < max(3, top_score * 0.45):
            continue
        selected.append(label)
        if len(selected) >= limit:
            break
    return selected
