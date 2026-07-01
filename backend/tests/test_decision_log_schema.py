"""DecisionLogResponse schema 的正确性测试。

重点验证：当从 ORM 实例 (DecisionLog) 序列化时，metadata 字段应读取
模型上的 metadata_ 属性（JSONB 列），而非 SQLAlchemy 保留的 MetaData 对象。
"""
import uuid
from datetime import datetime, timezone

from app.models.decision_log import DecisionLog
from app.schemas.decision_log import DecisionLogResponse


def _make_orm_instance() -> DecisionLog:
    """构造一个内存中的 DecisionLog ORM 实例（无需数据库）。"""
    now = datetime.now(timezone.utc)
    return DecisionLog(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        result_id=uuid.uuid4(),
        stage="risk",
        decision_type="risk_identified",
        source_phrase="示例原文",
        target_phrase="示例译文",
        decision="replace",
        reasoning="高风险文化词",
        confidence="high",
        metadata_={"risk_level": "high"},  # JSONB 列值，注意是 metadata_
        created_at=now,
    )


def test_metadata_reads_jsonb_column_from_orm():
    """from_attributes 应读取 metadata_（JSONB），而非 SQLAlchemy 的 MetaData。"""
    orm = _make_orm_instance()

    response = DecisionLogResponse.model_validate(orm)

    assert response.metadata == {"risk_level": "high"}


def test_metadata_json_output_key_is_metadata():
    """序列化输出的 JSON key 必须是 metadata（API 契约），不能是 metadata_。"""
    orm = _make_orm_instance()

    response = DecisionLogResponse.model_validate(orm)
    dumped = response.model_dump()

    assert "metadata" in dumped
    assert dumped["metadata"] == {"risk_level": "high"}
    assert "metadata_" not in dumped


def test_metadata_json_by_alias_emits_metadata():
    """FastAPI 的 APIRoute 默认 response_model_by_alias=True，
    所以 model_dump(by_alias=True) 必须输出 key metadata（而非 metadata_）。
    这是 FastAPI 实际序列化响应的路径。"""
    orm = _make_orm_instance()

    response = DecisionLogResponse.model_validate(orm)
    dumped = response.model_dump(by_alias=True)

    assert "metadata" in dumped
    assert dumped["metadata"] == {"risk_level": "high"}
    assert "metadata_" not in dumped
