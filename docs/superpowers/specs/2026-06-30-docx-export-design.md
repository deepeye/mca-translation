# .docx 导出功能设计文档

**版本:** v1.0
**日期:** 2026-06-30
**对应 PRD:** 第八章 8.1 / 第九章 P1

---

## 1. 概述

在现有 `.txt` 导出基础上增加 `.docx` 导出，满足用户将翻译结果以正式文档格式提交给编辑或合作方的需求（PRD 8.1）。

---

## 2. 架构

```
Frontend (ResultActions) → POST /api/export/docx → Backend (export_docx.py)
                                                         ↓
                                                   Response: .docx binary
                                                         ↓
                                                   Frontend 下载
```

后端生成，前端仅触发下载。无 DB 读写，无 Celery，无 LLM 调用。

---

## 3. 后端设计

### 3.1 新增文件

`backend/app/services/export_docx.py`

使用 `python-docx`（已在 `requirements.txt` 中）生成 Word 文档。

### 3.2 文档结构（标准版）

```
+-------------------------------------------+
| 标题: 翻译结果 - {language}               |
|                                           |
| 【原文】  ← Heading 2                     |
| (原文内容)  ← Normal                      |
|                                           |
| ---  ← 分隔线                             |
|                                           |
| 【译文】  ← Heading 2                     |
| (译文内容)  ← Normal                      |
|                                           |
| 如果有风险标注:                           |
|   风险词句 → Word 批注                    |
|   批注内容: [风险: high] 说明文字          |
+-------------------------------------------+
```

- 字体：中文用宋体（SimSun），英文用 Times New Roman
- 字号：12pt（小四）
- 标题：14pt，加粗
- 页面：A4，标准页边距

### 3.3 风险标注 → Word 批注

将风险标注转换为 Word 原生批注（comment），挂在译文对应词句上：

| 风险字段 | 批注内容 |
|---------|---------|
| `risk_level` | 显示为 `[风险: high]` |
| `risk_type` | 追加在风险等级后 |
| `explanation` | 换行显示 |

批注作者显示为 `CulturalBridge`。

### 3.4 API 端点

`POST /api/export/docx`

**Request:**
```json
{
  "source_text": "原文内容",
  "translated_text": "译文内容",
  "risk_annotations": [
    {
      "phrase": "短语",
      "risk_level": "high",
      "risk_type": "political_sensitivity",
      "explanation": "说明"
    }
  ],
  "language": "en-GB"
}
```

**Response:** `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`

直接返回二进制流，无 JSON 封装。文件名: `translation_{language}_{timestamp}.docx`

### 3.5 错误处理

- `translated_text` 为空 → 400 `translated_text is required`
- python-docx 内部异常 → 500 `Failed to generate document`

---

## 4. 前端设计

### 4.1 ApiClient 新增方法

```typescript
async exportDocx(data: ExportDocxRequest): Promise<Blob>
```

POST `/api/export/docx`，设置 `Accept: application/vnd.openxmlformats-officedocument.wordprocessingml.document`，返回 `Blob`。

### 4.2 ResultActions 新增按钮

现有 UI (result-actions.tsx):
```
[复制] [导出 .txt]
```

改为:
```
[复制] [导出 .txt] [导出 .docx]
```

`.docx` 按钮与 `.txt` 按钮共用 disabled 逻辑（无译文时禁用）。

下载方式：`window.URL.createObjectURL(blob)` + 模拟点击下载。

### 4.3 文件命名

`translation_{language}_{timestamp}.docx`

示例: `translation_en-GB_20260630_143022.docx`

---

## 5. 依赖

| 依赖 | 版本 | 用途 | 状态 |
|------|------|------|------|
| python-docx | >=1.1.2 | 生成 .docx | ✅ 已安装 |

无需新增任何依赖。

---

## 6. 不做的事

- 不修改 DB schema
- 不涉及 Celery 任务
- 不调用 LLM
- 不做批量 .docx 导出（属 P2 批量处理范畴）
- 不做 Word 模板/样式自定义
- 不生成 PDF（PRD P2）

---

## 7. 测试

- 单元测试: `backend/tests/test_export_docx.py`
  - 生成 .docx 后验证段落数 ≥ 2（原文段 + 译文段）
  - 有风险标注时验证批注数量匹配
  - 无风险标注时验证文档仍正常生成
