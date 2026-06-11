"""
AI 助手 API - 智能分析、图表推荐、NL2SQL、异常检测

提供:
- POST /ai/analyze            — 分析数据集数据
- POST /ai/chart-recommend    — 推荐图表类型
- POST /ai/auto-title         — 生成图表标题
- POST /ai/suggest-questions  — 建议自然语言问题
- POST /ai/nl2sql             — 自然语言转SQL
- POST /ai/anomaly-detect     — 检测数据异常
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.services import ai_service, dataset_service, nl2sql_service
from app.utils.response import success_response

router = APIRouter(prefix="/ai", tags=["AI助手"])


# ============================================================================
# Request / Response schemas
# ============================================================================


class AnalyzeRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="目标数据集ID")
    limit: int = Field(default=500, ge=1, le=10000, description="分析数据行数上限")


class ChartRecommendRequest(BaseModel):
    dataset_id: Optional[str] = Field(default=None, description="数据集ID (与columns_info二选一)")
    columns_info: Optional[list[dict]] = Field(default=None, description="列元数据列表 (与dataset_id二选一)")


class AutoTitleRequest(BaseModel):
    chart_config: dict = Field(..., description="图表配置，至少包含 chart_type, metrics, dimensions")


class SuggestQuestionsRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="目标数据集ID")


class NL2SQLRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="自然语言查询")
    dataset_id: str = Field(..., min_length=1, description="目标数据集ID")


class AnomalyDetectRequest(BaseModel):
    values: list[float] = Field(..., min_length=4, description="待检测的数值列表")


class FeedbackRequest(BaseModel):
    history_id: str = Field(..., description="查询历史记录ID")
    feedback: str = Field(..., pattern="^(positive|negative|neutral)$", description="反馈类型")


# ============================================================================
# 1. POST /ai/analyze — 智能数据分析
# ============================================================================


@router.post("/analyze", summary="分析数据集数据")
async def analyze(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """对数据集的数据执行智能统计分析。

    返回统计摘要 (summary)、趋势检测 (trends)、异常点 (anomalies)
    及中文自然语言洞察 (insights)。
    """
    # 加载数据集
    ds = await dataset_service.get_dataset(db, req.dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")

    # 获取数据预览
    try:
        preview = await dataset_service.preview_data(db, req.dataset_id, limit=req.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"数据查询失败: {exc}")

    rows = preview.get("rows", [])
    if not rows:
        return success_response(data={
            "summary": {},
            "trends": [],
            "anomalies": [],
            "insights": ["数据集当前无数据，无法分析"],
        })

    try:
        result = await ai_service.analyze_data(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分析失败: {exc}")

    return success_response(data=result)


# ============================================================================
# 2. POST /ai/chart-recommend — 图表类型推荐
# ============================================================================


@router.post("/chart-recommend", summary="推荐图表类型")
async def chart_recommend(
    req: ChartRecommendRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """根据数据特征推荐最佳图表类型。

    可通过 dataset_id 或 columns_info 提供列信息。
    返回推荐类型、置信度、理由及备选方案。
    """
    # 解析 columns_info
    columns_info = req.columns_info

    if not columns_info and req.dataset_id:
        # 从数据集加载列信息
        ds = await dataset_service.get_dataset(db, req.dataset_id)
        if not ds:
            raise HTTPException(status_code=404, detail="数据集不存在")
        cols = await dataset_service.get_dataset_columns(db, req.dataset_id)
        columns_info = _columns_to_info_list(cols)

        if not columns_info:
            raise HTTPException(status_code=400, detail="数据集没有配置字段信息，请先导入字段")

    if not columns_info:
        raise HTTPException(
            status_code=400,
            detail="请提供 dataset_id 或 columns_info",
        )

    try:
        result = await ai_service.recommend_chart(columns_info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"图表推荐失败: {exc}")

    return success_response(data={
        "chart_type": result["recommended_type"],
        "confidence": result["confidence"],
        "reason": result["reason"],
        "alternatives": result["alternatives"],
    })


# ============================================================================
# 3. POST /ai/auto-title — 自动生成图表标题
# ============================================================================


@router.post("/auto-title", summary="生成图表标题")
async def auto_title(
    req: AutoTitleRequest,
    _user: User = Depends(get_current_active_user),
):
    """根据图表配置自动生成有意义的中文标题。

    图表配置需至少包含 chart_type、metrics 和 dimensions 字段。
    返回多个候选标题。
    """
    chart_config = req.chart_config

    if not chart_config:
        raise HTTPException(status_code=400, detail="chart_config 不能为空")

    try:
        title = await ai_service.auto_title(chart_config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"标题生成失败: {exc}")

    # 生成 2-3 个变体标题作为候选
    titles = [title]

    # 变体1: 不带图表类型后缀
    chart_type = chart_config.get("chart_type", "")
    if chart_type and title.endswith(_chart_type_label(chart_type)):
        titles.append(title[:-len(_chart_type_label(chart_type))].rstrip("的"))

    # 变体2: 添加"分析概览"后缀
    if not title.endswith("分析概览"):
        base = title.rstrip("趋势图柱状图饼图散点图面积图雷达图地图矩形树图")
        titles.append(f"{base}分析概览")

    # 去重保留顺序
    seen: set[str] = set()
    unique: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    titles = unique[:3]

    return success_response(data={"titles": titles})


# ============================================================================
# 4. POST /ai/suggest-questions — 智能提问建议
# ============================================================================


@router.post("/suggest-questions", summary="建议自然语言问题")
async def suggest_questions(
    req: SuggestQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_active_user),
):
    """根据数据集结构生成 3-5 条自然语言提问建议。

    基于列元数据的数据类型、维度/指标角色分析，生成有针对性的分析问题。
    """
    # 加载数据集
    ds = await dataset_service.get_dataset(db, req.dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")

    # 加载列信息
    cols = await dataset_service.get_dataset_columns(db, req.dataset_id)
    if not cols:
        raise HTTPException(status_code=400, detail="数据集没有配置字段信息，请先导入字段")

    columns_info = _columns_to_info_list(cols)

    try:
        questions = await ai_service.suggest_questions(columns_info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"问题生成失败: {exc}")

    return success_response(data={"questions": questions})


# ============================================================================
# 5. POST /ai/nl2sql — 自然语言转SQL (核心亮点)
# ============================================================================


@router.post("/nl2sql", summary="自然语言转SQL")
async def nl2sql(
    req: NL2SQLRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """将自然语言查询转换为 SQL 语句。

    这是 DataVision 的核心亮点功能。接收用户的自然语言问题（如"各地区的销售额是多少"），
    结合数据集的 schema 信息和样本数据，通过 LLM 生成对应的 SQL SELECT 语句，
    并推荐最佳的图表类型。
    """
    try:
        result = await nl2sql_service.generate_sql(
            prompt=req.prompt,
            dataset_id=req.dataset_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # 持久化到查询历史
    try:
        await nl2sql_service.save_query_history(
            db=db,
            user_id=user.id,
            prompt=req.prompt,
            result=result,
        )
    except Exception:
        # 历史记录保存失败不应影响主响应
        pass

    return success_response(data={
        "sql": result["sql"],
        "chart_type": result["chart_type"],
        "confidence": result["confidence"],
    })


# ============================================================================
# 6. POST /ai/anomaly-detect — 异常值检测
# ============================================================================


@router.post("/anomaly-detect", summary="检测数据异常")
async def anomaly_detect(
    req: AnomalyDetectRequest,
    _user: User = Depends(get_current_active_user),
):
    """对一组数值进行异常值检测。

    使用 IQR (四分位距) 方法检测异常数据点。
    返回异常值列表，包含索引、值、偏离度和检测方法。
    """
    if len(req.values) < 4:
        raise HTTPException(
            status_code=400,
            detail="至少需要 4 个数值才能进行异常检测",
        )

    try:
        from app.core.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector()
        detected = detector.detect(req.values, method="iqr")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"异常检测失败: {exc}")

    anomalies = []
    for item in detected:
        if item.get("is_anomaly"):
            anomalies.append({
                "index": item["index"],
                "value": item["value"],
                "deviation_score": item["deviation_score"],
                "method": item["method"],
            })

    # 按偏离度降序排列
    anomalies.sort(key=lambda a: abs(a["deviation_score"]), reverse=True)

    return success_response(data={"anomalies": anomalies})


@router.get("/nl2sql/history", summary="NL查询历史")
async def get_nl2sql_history(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user: User = Depends(get_current_active_user),
    db=Depends(get_db),
):
    """获取当前用户的 NL2SQL 查询历史记录。"""
    total, records = await nl2sql_service.get_query_history(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "dataset_id": r.dataset_id,
            "prompt": r.prompt,
            "generated_sql": r.generated_sql,
            "chart_type": r.chart_type,
            "is_valid": r.is_valid,
            "feedback": r.feedback,
            "error_message": r.error_message,
            "execution_time_ms": r.execution_time_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    })


@router.post("/nl2sql/feedback", summary="提交NL查询反馈")
async def submit_nl2sql_feedback(
    req: FeedbackRequest,
    user: User = Depends(get_current_active_user),
    db=Depends(get_db),
):
    """对 NL2SQL 生成的查询结果提交反馈（正面/负面/中性）。"""
    ok = await nl2sql_service.submit_feedback(
        db=db,
        history_id=req.history_id,
        feedback=req.feedback,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="查询历史记录不存在")
    return success_response(message="反馈已提交")


# ============================================================================
# 内部辅助函数
# ============================================================================


def _columns_to_info_list(cols) -> list[dict]:
    """将 DatasetColumn ORM 对象列表转换为 ai_service 所需的 dict 列表。"""
    result = []
    for c in cols:
        result.append({
            "name": c.column_name,
            "column_name": c.column_name,
            "field": c.column_name,
            "data_type": c.data_type,
            "type": c.data_type,
            "alias": c.alias,
            "label": c.alias or c.column_name,
            "display_name": c.alias or c.column_name,
            "is_dimension": c.is_dimension,
            "is_metric": c.is_metric,
            "default_aggregation": c.default_aggregation,
            "semantic_type": c.semantic_type,
        })
    return result


_CHART_TYPE_LABEL_MAP = {
    "line": "趋势图",
    "bar": "柱状图",
    "pie": "饼图",
    "scatter": "散点图",
    "area": "面积图",
    "radar": "雷达图",
    "map": "地图",
    "treemap": "矩形树图",
    "table": "表格",
    "heatmap": "热力图",
    "funnel": "漏斗图",
    "gauge": "仪表盘",
    "number": "数字卡片",
    "combo": "组合图",
    "sankey": "桑基图",
    "wordcloud": "词云",
}


def _chart_type_label(chart_type: str) -> str:
    """图表类型 -> 中文标签。"""
    return _CHART_TYPE_LABEL_MAP.get(chart_type, "")
