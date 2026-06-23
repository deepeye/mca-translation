from app.services.glossary_classification import classify_system_glossary_term


def test_classify_political_discourse():
    assert classify_system_glossary_term("高质量共建一带一路") == "political_discourse"


def test_classify_institution_event():
    assert classify_system_glossary_term("2023中关村论坛") == "institution_event"


def test_classify_texts_documents():
    assert classify_system_glossary_term("《北征》") == "texts_documents"
    assert classify_system_glossary_term("2024年中央一号文件") == "texts_documents"


def test_classify_historical_culture():
    assert classify_system_glossary_term("龙的子孙") == "historical_culture"


def test_classify_cultural_site():
    assert classify_system_glossary_term("妇好墓") == "cultural_site"


def test_classify_food_cuisine():
    assert classify_system_glossary_term("兰州牛肉面") == "food_cuisine"


def test_classify_material_craft_medicine():
    assert classify_system_glossary_term("党参") == "material_craft_medicine"
    assert classify_system_glossary_term("汝瓷烧制技艺") == "material_craft_medicine"


def test_classify_geography_place():
    assert classify_system_glossary_term("中国台湾海峡") == "geography_place"


def test_classify_translation_driven_policy_discourse():
    assert classify_system_glossary_term("“两个维护”", "Two Upholds") == "political_discourse"


def test_classify_default_falls_back_to_political_discourse():
    assert classify_system_glossary_term("义兴张") == "political_discourse"
