TEXT_MARKERS = ("《", "》")
TEXT_KEYWORDS = ("文件", "报告", "条约", "条例", "纲要", "方案", "宣言", "协定", "规划")
TEXT_TRANSLATION_KEYWORDS = (
    "report",
    "plan",
    "action plan",
    "agreement",
    "treaty",
    "regulations",
    "declaration",
    "outline",
    "initiative",
)
SITE_CONTAINS = (
    "石窟",
    "遗址",
    "王陵",
    "书院",
    "塔林",
    "古道",
    "观星台",
    "测景台",
    "建筑群",
    "宫殿",
    "宗庙",
    "故宫",
    "城址",
    "陵墓",
    "龙门石窟",
    "云冈石窟",
    "麦积山石窟",
    "少林寺",
    "白马寺",
    "嵩岳寺塔",
    "殷墟",
    "故城",
    "古城",
)
SITE_ENDS = ("寺", "庙", "阙", "塔", "墓", "峡")
SITE_TRANSLATION_KEYWORDS = (
    "temple",
    "grottoes",
    "site",
    "tomb",
    "palace",
    "pagoda",
    "observatory",
    "academy",
    "ruins",
    "ancient city",
)
FOOD_CUISINE_KEYWORDS = (
    "烩面",
    "炸酱面",
    "担担面",
    "热干面",
    "牛肉面",
    "毛尖茶",
    "糖蒜",
    "高汤",
    "老汤",
    "粉条",
    "千张丝",
)
FOOD_TRANSLATION_KEYWORDS = ("noodles", "tea", "garlic", "soup")
MATERIAL_CRAFT_MEDICINE_KEYWORDS = (
    "瓷",
    "制瓷",
    "烧制技艺",
    "工艺",
    "药",
    "本草",
    "当归",
    "黄芪",
    "党参",
    "白芷",
    "枸杞",
    "怀山药",
    "怀菊花",
    "怀参",
    "怀地黄",
)
MATERIAL_TRANSLATION_KEYWORDS = (
    "porcelain",
    "materia medica",
    "medicine",
    "technique",
    "craft",
    "root",
    "angelica",
    "ginseng",
    "wolfberry",
    "yam",
    "chrysanthemum",
)
GEOGRAPHY_PLACE_KEYWORDS = ("河", "山", "湖", "海峡", "高原", "草原", "运河", "口岸")
GEOGRAPHY_TRANSLATION_KEYWORDS = (
    "river",
    "mountain",
    "lake",
    "strait",
    "plateau",
    "grassland",
    "gorge",
    "canal",
    "pass",
    "border crossing",
)
INSTITUTION_KEYWORDS = (
    "委员会",
    "研究所",
    "联盟",
    "论坛",
    "工作领导小组",
    "理事会",
    "合作机制",
    "代表大会",
    "研究中心",
    "科学院",
    "法院",
    "检察院",
    "政府",
    "工作委员会",
    "常委会",
    "峰会",
    "博览会",
    "交易会",
    "会议",
    "研讨会",
)
INSTITUTION_TRANSLATION_KEYWORDS = (
    "forum",
    "summit",
    "conference",
    "meeting",
    "expo",
    "exposition",
    "fair",
    "ceremony",
    "government",
    "committee",
    "academy",
    "association",
    "league",
    "center",
    "institute",
    "court",
)
HISTORY_CULTURE_KEYWORDS = (
    "文化",
    "佛教",
    "禅宗",
    "龙",
    "华夏",
    "仰韶",
    "甲骨",
    "牡丹",
    "律诗",
    "诗风",
    "古体",
    "春望",
    "登高",
    "北征",
    "春秋",
    "战国",
    "西周",
    "北魏",
    "隋唐",
    "秦汉",
    "明清",
    "商朝",
    "汉朝",
    "唐朝",
    "宋代",
    "清代",
    "夏朝",
    "王朝",
    "古代",
    "古都",
    "都城",
    "民族",
    "治乱兴衰",
    "名刹",
    "天地之中",
    "殷商",
    "中原",
    "传人",
    "子孙",
)
HISTORY_TRANSLATION_KEYWORDS = (
    "culture",
    "buddh",
    "dynasty",
    "poetry",
    "ethnic",
    "heritage",
    "civilization",
    "dragon",
    "ancient capitals",
)
POLICY_KEYWORDS = (
    "一带一路",
    "倡议",
    "建设",
    "合作",
    "发展",
    "规划",
    "战略",
    "共同体",
    "现代化",
    "生产力",
    "民主",
    "富裕",
    "体制",
    "自信",
    "五位一体",
    "全过程",
    "命运",
    "高质量",
    "主题教育",
    "港人治港",
    "澳人治澳",
    "一国两制",
    "分离",
    "扶贫",
    "抗疫",
    "治理",
    "国家安全",
    "制度",
    "行动方案",
    "共识",
    "意识",
    "理念",
    "目标",
    "改革",
    "精神",
    "模式",
    "体系",
    "责任制",
    "问题",
    "工程",
    "行动",
    "巡视",
    "维护",
)
POLICY_TRANSLATION_KEYWORDS = (
    "consensus",
    "goal",
    "campaign",
    "education",
    "reform",
    "model",
    "initiative",
    "management",
    "innovation",
    "consciousness",
    "poverty",
    "security",
    "governance",
    "system",
    "policy",
    "cooperation",
    "development",
    "strategy",
    "modernization",
    "mission",
    "upholds",
    "targeted",
    "centenary",
)


def _contains_translation_keyword(preferred_translation: str, keywords: tuple[str, ...]) -> bool:
    normalized_translation = f" {preferred_translation.lower()} "
    for keyword in keywords:
        if f" {keyword.lower()} " in normalized_translation:
            return True
    return False


def classify_system_glossary_term(source_term: str, preferred_translation: str = "") -> str:
    if any(marker in source_term for marker in TEXT_MARKERS) or any(
        source_term.endswith(keyword) or keyword in source_term for keyword in TEXT_KEYWORDS
    ) or _contains_translation_keyword(preferred_translation, TEXT_TRANSLATION_KEYWORDS):
        return "texts_documents"
    if any(keyword in source_term for keyword in FOOD_CUISINE_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, FOOD_TRANSLATION_KEYWORDS
    ):
        return "food_cuisine"
    if any(keyword in source_term for keyword in MATERIAL_CRAFT_MEDICINE_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, MATERIAL_TRANSLATION_KEYWORDS
    ):
        return "material_craft_medicine"
    if any(keyword in source_term for keyword in GEOGRAPHY_PLACE_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, GEOGRAPHY_TRANSLATION_KEYWORDS
    ):
        return "geography_place"
    if any(keyword in source_term for keyword in SITE_CONTAINS) or any(
        source_term.endswith(suffix) for suffix in SITE_ENDS
    ) or _contains_translation_keyword(preferred_translation, SITE_TRANSLATION_KEYWORDS):
        return "cultural_site"
    if any(keyword in source_term for keyword in INSTITUTION_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, INSTITUTION_TRANSLATION_KEYWORDS
    ):
        return "institution_event"
    if any(keyword in source_term for keyword in HISTORY_CULTURE_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, HISTORY_TRANSLATION_KEYWORDS
    ):
        return "historical_culture"
    if any(keyword in source_term for keyword in POLICY_KEYWORDS) or _contains_translation_keyword(
        preferred_translation, POLICY_TRANSLATION_KEYWORDS
    ):
        return "political_discourse"
    return "political_discourse"
