SYSTEM_GLOSSARY_TERM_TYPES = (
    "political_discourse",
    "institution_event",
    "texts_documents",
    "historical_culture",
    "cultural_site",
    "food_cuisine",
    "material_craft_medicine",
    "geography_place",
    "other_specialized",
    "cultural_metaphor",
    "idiom",
)

USER_GLOSSARY_TERM_TYPES = (
    "user_defined",
    "brand",
    "project",
)

SYSTEM_GLOSSARY_TERM_TYPE_LABELS = {
    "political_discourse": "政治话语",
    "institution_event": "机构会议",
    "texts_documents": "文本文献",
    "historical_culture": "历史文化",
    "cultural_site": "文化地标",
    "food_cuisine": "饮食特产",
    "material_craft_medicine": "工艺医药物产",
    "geography_place": "地理地点",
    "other_specialized": "其他专名",
    "cultural_metaphor": "文化隐喻",
    "idiom": "成语习语",
}

USER_GLOSSARY_TERM_TYPE_LABELS = {
    "user_defined": "用户自定义",
    "brand": "品牌术语",
    "project": "项目术语",
}

SYSTEM_GLOSSARY_TERM_TYPE_ORDER = (
    "political_discourse",
    "institution_event",
    "texts_documents",
    "historical_culture",
    "cultural_site",
    "food_cuisine",
    "material_craft_medicine",
    "geography_place",
    "other_specialized",
    "cultural_metaphor",
    "idiom",
)

LEGACY_SYSTEM_GLOSSARY_TERM_TYPES = (
    "political_discourse",
    "historical_culture",
    "institution_event",
    "texts_documents",
    "cultural_site",
)


def is_valid_system_term_type(value: str) -> bool:
    return value in SYSTEM_GLOSSARY_TERM_TYPES


def is_valid_user_term_type(value: str) -> bool:
    return value in USER_GLOSSARY_TERM_TYPES
