# 文化语境适配设计

**日期：** 2026-06-16
**状态：** 设计定稿
**作者：** brainstorming session

## 背景

当前系统只有 strategy（信息等值/受众优先/直译参考）和 genre（政治/新闻/政策/品牌）两个维度影响翻译输出，缺少"目标受众文化背景"这个核心维度。

外宣场景下，"中文 → 英文"的语言转换不足以解决"中国叙事 → 海外受众能理解、接受、愿意传播的表达"这一传播效果问题。本设计在现有翻译流程中引入**文化语境**维度，渐进式增强系统的跨文化适配能力，而不重构整体架构。

## 目标

1. 让用户在翻译时显式选择**目标文化圈**和**受众类型**
2. 在主翻译之前新增**预处理步骤**，自动识别文化负载词并生成本土化约束
3. 在主翻译 prompt 中注入文化圈特征、受众要求和术语约束
4. 在翻译结果中向用户展示文化适配过程（哪些词被识别、采用何种策略、为什么）
5. 完全向后兼容：不选文化圈时行为与现有一致

## 非目标

本设计**不**包含以下能力（属于后续迭代或独立子项目）：

- 术语知识库 / RAG（方案 B 的术语库部分）
- 文化负载词的源文本内联高亮
- 多种风格版本输出（媒体版/社交版/学术版/字幕版）
- 海外认知数据资产建设
- 文化距离量化评分模型（BERT 分类器）
- 决策日志（DecisionLog）

## 核心设计决策

### 决策 1：文化语境作为新增维度，策略保留

新流程：`输入文本 → 选择文体 → 选择文化圈 → 选择受众类型 → 选择策略 → 翻译`

文化圈和受众类型是新增维度，与现有策略并列。两个维度分开选择（不合并为单一选项），便于灵活组合。

### 决策 2：文化圈和受众类型分别建模

| 维度 | 影响什么 |
|------|---------|
| 文化圈（cultural_sphere） | 概念解释深度、价值观差异、禁忌词 |
| 受众类型（audience_type） | 表达风格、深度、正式程度 |

合并会产生 8×6=48 个选项，分开则维度清晰、组合灵活。

### 决策 3：纯 LLM 预处理（方案 A）

新增一次 LLM 调用 `cultural_preprocess`，让大模型根据文化圈+受众类型+文体识别文化负载词并生成本土化约束。不依赖术语数据库，不增加运维复杂度。

未来若建设术语知识库，可无缝替换或增强此步骤。

### 决策 4：可选维度，向后兼容

新增的 `cultural_sphere` 和 `audience_type` 字段在数据库中可为 NULL。未传值时跳过预处理步骤，行为与现有完全一致。

## 架构

### 流程对比

**现有流程：**
```
源文本
  ↓
[主翻译 LLM 调用]
  ↓
[风险标注 LLM 调用]
  ↓
返回结果
```

**新流程：**
```
源文本 + 文化圈 + 受众类型 + 文体 + 策略
  ↓
[文化预处理 LLM 调用]  ← 新增
  ↓ culture_loaded_terms + cultural_notes + taboo_warnings
[主翻译 LLM 调用]（带文化约束的 prompt）
  ↓
[风险标注 LLM 调用]
  ↓
返回结果（含 cultural_adaptation 字段）
```

如果未选择文化圈，跳过预处理步骤，主翻译 prompt 中不注入文化约束段。

## 数据模型

### 枚举：文化圈（CulturalSphere）

| key | 中文标签 | 覆盖国家/地区 |
|-----|---------|--------------|
| `western_english` | 欧美英语圈 | 美国、英国、加拿大、澳大利亚 |
| `european_continental` | 欧洲大陆 | 德国、法国、意大利、北欧 |
| `islamic_middle_east` | 伊斯兰中东 | 沙特、阿联酋、伊朗、埃及 |
| `east_asian_confucian` | 东亚儒家 | 日本、韩国 |
| `latin_american` | 拉美 | 巴西、墨西哥、阿根廷 |
| `russian_sphere` | 俄语圈 | 俄罗斯、中亚 |
| `south_asian` | 南亚 | 印度、巴基斯坦、孟加拉 |
| `african` | 非洲 | 南非、尼日利亚、肯尼亚 |

### 枚举：受众类型（AudienceType）

| key | 中文标签 | 表达特点 |
|-----|---------|---------|
| `general_public` | 公众 | 简明、故事化、避免术语、日常类比 |
| `media` | 媒体 | 客观、5W1H、Reuters 风格、可引用 |
| `government` | 政府 | 正式、精准、政策语言、避免歧义 |
| `academic` | 学术 | 概念完整、引用规范、论证严密 |
| `business` | 企业 | 数据驱动、商业语言、ROI 视角 |
| `diaspora_chinese` | 海外华人 | 文化共鸣+当地语境、可保留部分中文概念 |

### 枚举：本土化策略（AdaptationStrategy）

| key | 说明 | 适用场景 |
|-----|------|---------|
| `literal` | 直译 | 文化距离低、概念通用（如"熊猫"） |
| `explanatory` | 解释型翻译 | 概念存在但缺少背景（如"共同富裕"） |
| `analogical` | 类比翻译 | 目标文化有类似概念（如"科举"→"civil service exam"） |
| `reconstruction` | 场景重构 | 整体表达方式需要改变 |

### 后端数据模型变更

**`TranslationJob` 表新增字段：**
```sql
ALTER TABLE translation_jobs 
ADD COLUMN cultural_sphere VARCHAR(32) DEFAULT NULL,
ADD COLUMN audience_type VARCHAR(32) DEFAULT NULL;
```

**Pydantic Schema：**
```python
class CulturalLoadedTerm(BaseModel):
    term: str
    culture_gap: Literal["low", "medium", "high"]
    adaptation_strategy: Literal["literal", "explanatory", "analogical", "reconstruction"]
    suggested_rendering: str
    reason: str

class CulturalPreprocessResult(BaseModel):
    culture_loaded_terms: list[CulturalLoadedTerm]
    cultural_notes: list[str]
    taboo_warnings: list[str]

class CreateJobRequest(BaseModel):
    # ... 现有字段 ...
    cultural_sphere: Optional[str] = None
    audience_type: Optional[str] = None

class TranslationResultResponse(BaseModel):
    # ... 现有字段 ...
    cultural_adaptation: Optional[CulturalPreprocessResult] = None
```

### 前端类型变更

```typescript
// workspace-store.ts
export type CulturalSphere = 
  | "western_english"
  | "european_continental"
  | "islamic_middle_east"
  | "east_asian_confucian"
  | "latin_american"
  | "russian_sphere"
  | "south_asian"
  | "african";

export type AudienceType = 
  | "general_public"
  | "media"
  | "government"
  | "academic"
  | "business"
  | "diaspora_chinese";

export type AdaptationStrategy = 
  | "literal"
  | "explanatory"
  | "analogical"
  | "reconstruction";

export interface CulturalLoadedTerm {
  term: string;
  culture_gap: "low" | "medium" | "high";
  adaptation_strategy: AdaptationStrategy;
  suggested_rendering: string;
  reason: string;
}

export interface CulturalAdaptation {
  culture_loaded_terms: CulturalLoadedTerm[];
  cultural_notes: string[];
  taboo_warnings: string[];
}

// input 对象新增字段
interface WorkspaceInput {
  text: string;
  genre: Genre;
  strategy: Strategy;
  culturalSphere?: CulturalSphere;  // 新增
  audienceType?: AudienceType;       // 新增
}
```

## 文化预处理服务

### 新增文件

- `backend/app/llm/prompts.py` 中新增 `CULTURAL_PREPROCESS_PROMPT`
- `backend/app/services/cultural.py` —— 新增预处理服务模块

### 服务接口

```python
# backend/app/services/cultural.py

async def cultural_preprocess(
    text: str,
    cultural_sphere: str,
    audience_type: str,
    genre: str,
    llm_client,
) -> CulturalPreprocessResult:
    """预处理：识别文化负载词，生成本土化约束。
    
    输入：源文本 + 文化圈 + 受众类型 + 文体
    输出：CulturalPreprocessResult（文化负载词列表 + 文化注意事项 + 禁忌提醒）
    """
    prompt = build_cultural_preprocess_prompt(
        text, cultural_sphere, audience_type, genre
    )
    response = await llm_client.chat(prompt)
    return parse_cultural_preprocess_response(response)
```

### 预处理 Prompt 设计

`CULTURAL_PREPROCESS_PROMPT` 模板包含：

1. **角色定义** —— "你是一位资深的国际传播专家，擅长跨文化内容适配"
2. **任务说明** —— 识别源文本中的文化负载词，根据目标文化圈和受众类型给出本土化建议
3. **文化圈特征注入** —— 根据传入的 `cultural_sphere` 注入对应的特征段
4. **受众类型注入** —— 根据传入的 `audience_type` 注入表达要求
5. **文体注入** —— 根据 `genre` 调整识别侧重
6. **输出格式** —— 严格 JSON：
   ```json
   {
     "culture_loaded_terms": [
       {
         "term": "源文本中的词或短语",
         "culture_gap": "low|medium|high",
         "adaptation_strategy": "literal|explanatory|analogical|reconstruction",
         "suggested_rendering": "建议的目标语译法",
         "reason": "为什么需要这种适配"
       }
     ],
     "cultural_notes": ["文化注意事项1", "..."],
     "taboo_warnings": ["禁忌提醒1", "..."]
   }
   ```

### 文化圈特征知识表

每个文化圈对应一段硬编码的特征描述，注入预处理 prompt 和主翻译 prompt：

| 文化圈 | 注入内容（要点） |
|--------|----------------|
| 欧美英语圈 | 个人主义价值观、自由市场语境、对"国家主导"叙事天然警惕、偏好数据+案例论证 |
| 欧洲大陆 | 社会民主传统、重视制度对比、环保议题敏感、偏好深度分析 |
| 伊斯兰中东 | 宗教敏感、集体主义、权威尊重、避免宗教冲突表述、家庭价值观 |
| 东亚儒家 | 高语境文化、等级意识、集体和谐、对"发展"叙事接受度高 |
| 拉美 | 关系驱动、情感表达、发展议题、南南合作叙事 |
| 俄语圈 | 国家叙事传统、历史敏感、地缘政治意识强 |
| 南亚 | 多元宗教、发展中大国、英语普及、发展合作视角 |
| 非洲 | 发展合作、南南叙事、年轻人口、基础设施议题 |

实现上以一个常量字典 `CULTURAL_SPHERE_PROFILES: dict[str, str]` 存放，键为 `cultural_sphere` 的 key，值为详细描述段。

## 主翻译 Prompt 增强

### Prompt 结构变更

现有 `TRANSLATION_SYSTEM_PROMPT` 结构：
```
角色定义
规则1-7
{genre} 文体指导
{strategy_description} 策略描述
```

新结构（仅当传入 `cultural_constraints` 时增加 `<cultural_constraints>` 段）：
```
角色定义

<cultural_constraints>
[文化圈特征]（来自 CULTURAL_SPHERE_PROFILES）
[受众类型要求]（来自 AUDIENCE_TYPE_GUIDELINES）
[术语约束表]（来自预处理结果）
[文化注意事项]（来自预处理结果）
[禁忌提醒]（来自预处理结果）
</cultural_constraints>

规则1-7
{genre} 文体指导
{strategy_description} 策略描述
```

### 术语约束注入格式

预处理的 `culture_loaded_terms` 转化为如下格式注入：

```
术语约束（必须遵守）：
- "共同富裕" → MUST_USE 解释型翻译: "a policy initiative aimed at achieving more balanced wealth distribution while preserving market incentives"
  原因: Direct translation 'common prosperity' lacks context for Western audiences

术语约束（建议遵守）：
- "新质生产力" → SUGGEST 解释型翻译: "innovation-driven productive forces emphasizing technological advancement"
  原因: ...
```

约束级别由 `culture_gap` 决定：
- `high` → `MUST_USE`
- `medium` → `SUGGEST`
- `low` → 不生成约束（LLM 自行判断）

### Prompt 构建变更

```python
def build_translation_prompt(
    text: str,
    target_lang: str,
    genre: str,
    strategy: str,
    cultural_constraints: Optional[CulturalPreprocessResult] = None,  # 新参数
    cultural_sphere: Optional[str] = None,                            # 新参数
    audience_type: Optional[str] = None,                              # 新参数
) -> str:
    # 如果有 cultural_constraints，注入 <cultural_constraints> 段
    # 否则保持现有逻辑
```

## 翻译流程编排

`backend/app/services/translation.py` 的 `translate_content` 函数：

```python
async def translate_content(job: TranslationJob, ...):
    # ... 现有逻辑 ...
    
    # 新增步骤：文化预处理（仅当选择了文化圈）
    cultural_result = None
    if job.cultural_sphere:
        cultural_result = await cultural_preprocess(
            text=job.source_text,
            cultural_sphere=job.cultural_sphere,
            audience_type=job.audience_type or "general_public",
            genre=job.genre,
            llm_client=llm_client,
        )
    
    # 主翻译：传入文化约束
    translation = await call_translation_llm(
        text=job.source_text,
        target_lang=target_lang,
        genre=job.genre,
        strategy=job.strategy,
        cultural_constraints=cultural_result,
        cultural_sphere=job.cultural_sphere,
        audience_type=job.audience_type,
    )
    
    # 风险标注（现有，不变）
    risk_annotations = await annotate_risks(...)
    
    return TranslationResult(
        translation=translation,
        risk_annotations=risk_annotations,
        cultural_adaptation=cultural_result,  # 新字段
    )
```

## 前端交互设计

### 参数面板布局

在现有 strategy-selector 附近新增两个选择器：

```
┌─────────────────────────────────────┐
│  文体: [政治 v]                       │  ← 现有
│                                      │
│  文化圈: [欧美英语圈 v]               │  ← 新增
│                                      │
│  受众类型: [公众 v]                   │  ← 新增
│                                      │
│  翻译策略:                           │  ← 现有
│  ○ 信息等值  ○ 受众优先  ○ 直译参考   │
└─────────────────────────────────────┘
```

### 文化圈选择器

- 组件：Select/Dropdown
- 显示：中文标签
- 悬停 tooltip：覆盖国家列表 + 核心特征
- 默认值：`western_english`

### 受众类型选择器

- 组件：Select/Dropdown
- 显示：中文标签
- 悬停 tooltip：表达特点说明
- 默认值：`general_public`

### 翻译结果展示

在翻译结果面板新增"文化适配"可折叠区域，展示：

1. **识别的文化负载词列表**：每个词显示原文、适配策略、差异度、建议译法、原因
2. **文化注意事项**：列表展示
3. **禁忌提醒**：列表展示，使用 ⚠️ 或 🚫 图标突出

布局示例：

```
┌─────────────────────────────────────────┐
│  翻译结果                                │
│  [翻译文本...]                           │
│                                         │
│  ▼ 文化适配说明（共识别 3 个文化负载词）  │
│  ┌─────────────────────────────────┐    │
│  │ 共同富裕 [解释型翻译] [差异度: 高]│    │
│  │ 译法: "a policy initiative..."  │    │
│  │ 原因: ...                        │    │
│  │                                 │    │
│  │ 全过程人民民主 [类比翻译] [高]   │    │
│  │ ...                             │    │
│  │                                 │    │
│  │ ⚠️ 文化注意事项:                │    │
│  │ • 避免国家控制经济的表述框架     │    │
│  │                                 │    │
│  │ 🚫 禁忌提醒:                    │    │
│  │ • 避免宗教治理相关表述           │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ▼ 风险标注（现有）                      │
└─────────────────────────────────────────┘
```

### API 变更

**`POST /api/jobs/`** 请求体新增：
```json
{
  "text": "...",
  "genre": "political",
  "strategy": "audience_first",
  "cultural_sphere": "western_english",  // 新增，可选
  "audience_type": "general_public"      // 新增，可选
}
```

**翻译结果响应**新增 `cultural_adaptation` 字段（结构见 Schema 定义）。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 预处理 LLM 调用失败 | 降级：跳过预处理，主翻译 prompt 不注入文化约束，记录日志 |
| 预处理返回的 JSON 解析失败 | 同上：降级处理，不阻断主翻译 |
| 主翻译 LLM 调用失败 | 现有错误处理路径，无变化 |
| 用户未选择文化圈 | 跳过预处理，行为与现有完全一致（向后兼容） |
| 用户选择文化圈但未选受众类型 | 受众类型默认为 `general_public` |

## 测试策略

### 单元测试
- `cultural_preprocess` 服务对各文化圈+受众类型组合的 prompt 构建正确性
- `parse_cultural_preprocess_response` 对各种 LLM 响应格式的解析（包括异常情况）
- `build_translation_prompt` 在有/无 `cultural_constraints` 时的 prompt 构建差异

### 集成测试
- 完整翻译流程（含预处理）的端到端调用
- 预处理失败时的降级路径
- 不传文化圈时的向后兼容（与现有行为一致）

### 人工验证
- 同一段中文文本（如"共同富裕不是平均主义"）在不同文化圈+受众类型组合下的翻译差异
- 检查识别出的文化负载词是否符合预期
- 检查文化注意事项和禁忌提醒的合理性

## 实施顺序建议

1. **后端基础**：枚举定义、数据库迁移、Schema 扩展
2. **预处理服务**：`cultural.py` 服务、`CULTURAL_PREPROCESS_PROMPT` 模板、`CULTURAL_SPHERE_PROFILES` 知识表
3. **主翻译增强**：`build_translation_prompt` 增加 `cultural_constraints` 参数和注入逻辑
4. **翻译流程串联**：`translate_content` 编排预处理+主翻译+风险标注
5. **API 层**：`CreateJobRequest` 和 `TranslationResultResponse` 字段扩展
6. **前端类型与 store**：新增类型定义和 store 字段
7. **前端选择器**：文化圈选择器、受众类型选择器组件
8. **前端展示**：翻译结果面板新增"文化适配"区域

每步完成后可以独立验证。

## 未来扩展（不在本设计范围）

- 术语知识库（GlossaryEntry 模型 + pgvector 语义搜索）替换或增强 LLM 预处理
- 文化负载词在源文本中的内联高亮（蓝色下划线 + 悬停预览）
- 多种风格版本输出（媒体版/社交版/学术版/字幕版）
- 文化距离量化评分（0-100 的 Culture Gap Score）
- 决策日志（DecisionLog）记录每个翻译选择的理由
- 海外认知数据资产（不同国家对中国议题的关注点画像）
- 自动按目标语言推荐文化圈+受众类型默认值
