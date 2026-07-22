"""
src/agent/response_builder/response_builder.py
Converts a ToolExecutionResult into a renderer-ready AgentUIResponse.

This is the only module that instantiates AgentUIResponse.
No business logic lives here — only presentation decisions:
  • which UI type to render
  • which actions to attach
  • what human-readable message to compose

Bilingual (EN/AR): the reply language follows the user's message language —
an Arabic message gets Arabic reply text, action labels, and UI titles;
anything else keeps the original English byte-for-byte. Action `type` values,
tool names, and all data payloads are language-independent and unchanged.
Button-driven actions arrive without a message and default to English.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from src.schemas.agent import (
    ActionStyle,
    AgentAction,
    AgentUIComponent,
    AgentUIResponse,
    AgentUIType,
    ToolExecutionResult,
)

logger = logging.getLogger(__name__)

# Any character in the primary Arabic block marks the message as Arabic.
_AR_CHARS_RE = re.compile(r"[؀-ۿ]")


def _lang_of(message: str) -> str:
    """Return 'ar' when the user's message contains Arabic script, else 'en'."""
    return "ar" if _AR_CHARS_RE.search(message or "") else "en"


# ── Public entry point ────────────────────────────────────────────────────────

def build_response(
    result: ToolExecutionResult,
    original_message: str = "",
    original_action: Optional[AgentAction] = None,
) -> AgentUIResponse:
    """Dispatch to the appropriate builder based on tool name and success."""
    lang = _lang_of(original_message)

    if not result.success:
        return _error_response(result, lang)

    tool = result.tool_name
    data = result.data or {}

    # Use match statement for cleaner dispatch (Python 3.10+)
    match tool:
        case "get_ranked_jobs" | "search_jobs":
            response = _job_list_response(result, data, lang)
        case "apply_job":
            response = _apply_response(result, data, original_action, lang)
        case "skip_job":
            response = _skip_response(result, data, original_action, lang)
        case "save_job":
            response = _save_response(result, original_action, lang)
        case "block_company":
            response = _block_response(result, data, original_action, lang)
        case "get_application_stats":
            response = _stats_response(result, data, lang)
        case "get_pipeline_status":
            response = _pipeline_status_response(result, data, lang)
        case "trigger_pipeline":
            response = _pipeline_trigger_response(result, data, lang)
        case "get_market_trends":
            response = _market_insights_response(result, data, lang)
        case "get_application_strategy":
            response = _strategy_response(result, data, lang)
        case "get_learning_profile":
            response = _learning_profile_response(result, data, lang)
        case "help":
            response = _help_response(lang)
        case _:
            # Unknown tool — return raw data as text fallback
            response = AgentUIResponse(
                message=(f"نتيجة من {tool}." if lang == "ar" else f"Result from {tool}."),
                ui=AgentUIComponent(type=AgentUIType.TEXT, data=data),
                tool_used=tool,
                success=True,
            )

    logger.debug(
        "build_response",
        extra={
            "tool": result.tool_name,
            "success": result.success,
            "ui_type": response.ui.type.value if response.ui else "unknown",
        },
    )
    return response


# ── Individual builders ───────────────────────────────────────────────────────

def _job_list_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    jobs = data.get("jobs", [])
    total = data.get("total", 0)
    page = data.get("page", 1)
    page_size = data.get("page_size", 20)
    has_more = data.get("has_more", False)

    if not jobs:
        return AgentUIResponse(
            message=(
                "لا توجد وظائف مطابقة لمرشحاتك الحالية. جرّب خفض الحد الأدنى للنقاط من الإعدادات."
                if lang == "ar"
                else "No jobs match your current filters. Try lowering the minimum score in Settings."
            ),
            ui=AgentUIComponent(type=AgentUIType.TEXT, data={"hint": "no_results"}),
            tool_used=result.tool_name,
            success=True,
        )

    count = len(jobs)
    pages = (total + page_size - 1) // page_size
    if lang == "ar":
        message = (
            f"هذه أفضل {count} وظيفة مطابقة لك (صفحة {page} من {pages}). "
            "اضغط قدّم أو تخطَّ أو احفظ على كل بطاقة."
        )
        ui_title = f"أفضل {count} وظيفة مطابقة"
    else:
        message = (
            f"Here are your top {count} job match{'es' if count != 1 else ''} "
            f"(page {page} of {pages}). "
            "Click Apply, Skip, or Save on each card."
        )
        ui_title = f"Top {count} Matches"

    actions = _job_actions_for_list(jobs, lang)

    # Add pagination action if more results available
    if has_more:
        actions.append(
            AgentAction(
                type="load_more",
                label="حمّل المزيد من الوظائف" if lang == "ar" else "Load more jobs",
                style=ActionStyle.SECONDARY,
                metadata={"page": page + 1, "page_size": page_size},
            )
        )

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(
            type=AgentUIType.JOB_LIST,
            title=ui_title,
            data={"jobs": jobs, "total": total, "page": page, "has_more": has_more},
        ),
        actions=actions,
        tool_used=result.tool_name,
        success=True,
    )


def _job_actions_for_list(jobs: List[Dict[str, Any]], lang: str = "en") -> List[AgentAction]:
    """One Apply + Skip + Save action per job, labelled with the job title."""
    actions: List[AgentAction] = []
    for job in jobs:
        job_id = str(job.get("id", job.get("link", "")))
        title_short = (job.get("title") or "Job")[:40]

        actions.append(AgentAction(
            action_id=_deterministic_action_id("apply", job),
            type="apply",
            label=(f"قدّم — {title_short}" if lang == "ar" else f"Apply — {title_short}"),
            style=ActionStyle.PRIMARY,
            job_id=job_id,
            job=job,
        ))
        actions.append(AgentAction(
            action_id=_deterministic_action_id("skip", job),
            type="skip",
            label="تخطَّ" if lang == "ar" else "Skip",
            style=ActionStyle.SECONDARY,
            job_id=job_id,
            job=job,
        ))
        actions.append(AgentAction(
            action_id=_deterministic_action_id("save", job),
            type="save",
            label="احفظ" if lang == "ar" else "Save",
            style=ActionStyle.SECONDARY,
            job_id=job_id,
            job=job,
        ))
    return actions


def _apply_response(
    result: ToolExecutionResult,
    data: Dict[str, Any],
    action: Optional[AgentAction],
    lang: str = "en",
) -> AgentUIResponse:
    title = _job_title(action)
    status = data.get("status", "unknown")
    msg = data.get("message", "")

    if lang == "ar":
        if status in ("applied", "success"):
            message = f"تم التقديم بنجاح على **{title}**. {msg}"
        elif status == "dry_run":
            message = f"اكتمل التشغيل التجريبي لـ **{title}** — لم يُرسل أي نموذج. {msg}"
        elif status == "already_applied":
            message = f"سبق أن قدّمت على **{title}**."
        elif status == "unsupported":
            message = f"لا يوجد محرك تقديم آلي يدعم هذا المصدر. {msg}"
        else:
            message = f"محاولة تقديم على **{title}**: {msg or status}"
        ui_title = "نتيجة التقديم"
    else:
        if status in ("applied", "success"):
            message = f"Successfully applied to **{title}**. {msg}"
        elif status == "dry_run":
            message = f"Dry run complete for **{title}** — no form was submitted. {msg}"
        elif status == "already_applied":
            message = f"You have already applied to **{title}**."
        elif status == "unsupported":
            message = f"No automation engine supports this source. {msg}"
        else:
            message = f"Application attempt for **{title}**: {msg or status}"
        ui_title = "Application Result"

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(
            type=AgentUIType.CONFIRM,
            title=ui_title,
            data={"status": status, "title": title, **data},
        ),
        tool_used=result.tool_name,
        success=True,
    )


def _skip_response(
    result: ToolExecutionResult,
    data: Dict[str, Any],
    action: Optional[AgentAction],
    lang: str = "en",
) -> AgentUIResponse:
    title = _job_title(action)
    skipped = data.get("skipped", True)
    if lang == "ar":
        if skipped:
            message = f"تم تخطي **{title}**. لن تظهر في النتائج القادمة."
        else:
            message = f"**{title}** مسجلة مسبقاً — لا تغيير."
    else:
        if skipped:
            message = f"Skipped **{title}**. It won't appear in future results."
        else:
            message = f"**{title}** was already tracked — no change made."

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.CONFIRM, data={"skipped": skipped, "title": title}),
        tool_used=result.tool_name,
        success=True,
    )


def _save_response(
    result: ToolExecutionResult,
    action: Optional[AgentAction],
    lang: str = "en",
) -> AgentUIResponse:
    title = _job_title(action)
    return AgentUIResponse(
        message=(
            f"تم حفظ **{title}** للمراجعة لاحقاً." if lang == "ar"
            else f"Saved **{title}** for later review."
        ),
        ui=AgentUIComponent(type=AgentUIType.CONFIRM, data={"title": title}),
        tool_used=result.tool_name,
        success=True,
    )


def _block_response(
    result: ToolExecutionResult,
    data: Dict[str, Any],
    action: Optional[AgentAction],
    lang: str = "en",
) -> AgentUIResponse:
    # Fix: data is always a dict, extract company from it or fallback to action
    company = data.get("company") or _job_company(action)
    return AgentUIResponse(
        message=(
            (
                f"تم حظر **{company}**. ستُستبعد نتائج هذه الشركة من الآن فصاعداً. "
                "أضفها إلى EXCLUDE_KEYWORDS في .env لتثبيت الحظر بعد إعادة التشغيل."
            )
            if lang == "ar"
            else (
                f"Blocked **{company}**. Future results from this company will be suppressed. "
                "Add to EXCLUDE_KEYWORDS in .env to persist across restarts."
            )
        ),
        ui=AgentUIComponent(type=AgentUIType.CONFIRM, data={"blocked_company": company}),
        tool_used=result.tool_name,
        success=True,
    )


def _stats_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    total = data.get("total_applied", 0)
    interviews = data.get("interviews_scheduled", 0)
    rate = data.get("success_rate", 0.0)

    if lang == "ar":
        message = (
            f"قدّمت على **{total}** وظيفة. "
            f"عدد المقابلات المجدولة: **{interviews}** "
            f"(نسبة النجاح {rate}%)."
        )
        ui_title = "تقدم الطلبات"
        run_label = "شغّل الخط الآن"
    else:
        message = (
            f"You've applied to **{total}** jobs. "
            f"**{interviews}** interview{'s' if interviews != 1 else ''} scheduled "
            f"({rate}% success rate)."
        )
        ui_title = "Application Progress"
        run_label = "Run Pipeline Now"

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.STATS, title=ui_title, data=data),
        actions=[
            AgentAction(
                type="trigger_pipeline",
                label=run_label,
                style=ActionStyle.SECONDARY,
            )
        ],
        tool_used=result.tool_name,
        success=True,
    )


def _pipeline_status_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    status = data.get("status", "idle")
    started = data.get("started_at", "—")
    finished = data.get("finished_at")

    if lang == "ar":
        if status == "running":
            message = f"الخط **يعمل الآن** (بدأ: {started})."
        elif status == "done":
            message = f"اكتمل آخر تشغيل للخط عند {finished or started}."
        elif status == "failed":
            err = data.get("error", "خطأ غير معروف")
            message = f"**فشل** آخر تشغيل للخط: {err}"
        else:
            message = "لا توجد تشغيلات مسجلة للخط بعد."
        run_label = "شغّل الخط الآن"
    else:
        if status == "running":
            message = f"Pipeline is currently **running** (started: {started})."
        elif status == "done":
            message = f"Last pipeline run **completed** at {finished or started}."
        elif status == "failed":
            err = data.get("error", "unknown error")
            message = f"Last pipeline run **failed**: {err}"
        else:
            message = "No pipeline runs recorded yet."
        run_label = "Run Pipeline Now"

    actions = []
    if status != "running":
        actions.append(AgentAction(
            type="trigger_pipeline",
            label=run_label,
            style=ActionStyle.PRIMARY,
        ))

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.PIPELINE_STATUS, data=data),
        actions=actions,
        tool_used=result.tool_name,
        success=True,
    )


def _pipeline_trigger_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    return AgentUIResponse(
        message=(
            "بدأ تشغيل الخط. يعمل في الخلفية — تحقق من الحالة بعد دقيقة."
            if lang == "ar"
            else "Pipeline started. It runs in the background — check status in a minute."
        ),
        ui=AgentUIComponent(
            type=AgentUIType.PIPELINE_STATUS,
            data={"status": "running", **data},
        ),
        tool_used=result.tool_name,
        success=True,
    )


def _error_response(result: ToolExecutionResult, lang: str = "en") -> AgentUIResponse:
    error_msg = result.error or ("خطأ غير معروف" if lang == "ar" else "unknown error")
    return AgentUIResponse(
        message=(
            f"❌ {error_msg}. حاول مجدداً أو جرّب طلباً مختلفاً."
            if lang == "ar"
            else f"❌ {error_msg}. Try again or use a different request."
        ),
        ui=AgentUIComponent(
            type=AgentUIType.ERROR,
            data={"error": result.error, "tool": result.tool_name},
        ),
        actions=[
            AgentAction(
                type="help",
                label="المساعدة" if lang == "ar" else "Get Help",
                style=ActionStyle.SECONDARY,
            )
        ],
        tool_used=result.tool_name,
        success=False,
    )


def _help_response(lang: str = "en") -> AgentUIResponse:
    if lang == "ar":
        message = (
            "إليك ما يمكنك أن تطلبه مني:\n"
            "• **ورني أفضل وظائف اليوم** — وظائف مرتبة حسب المطابقة\n"
            "• **إحصائيات طلباتي** — تقرير التقدم\n"
            "• **حالة الخط** — معلومات آخر تشغيل\n"
            "• **شغّل الخط** — ابدأ البحث عن وظائف الآن\n"
            "• **رؤى السوق** — صحة سوق العمل الإماراتي واتجاهاته\n"
            "• **استراتيجية التقديم** — أسلوب تقديم مخصص لك\n"
            "• **ملف التعلم** — تفضيلاتك والأدوار المستنتجة\n"
            "\nأو اضغط قدّم / تخطَّ / احفظ على أي بطاقة وظيفة."
        )
        ui_title = "الأوامر المتاحة"
        commands = [
            "ورني أفضل وظائف اليوم",
            "إحصائيات طلباتي",
            "حالة الخط",
            "شغّل الخط",
            "رؤى السوق",
            "استراتيجية التقديم",
            "ملف التعلم",
        ]
    else:
        message = (
            "Here's what you can ask me:\n"
            "• **Show me today's best jobs** — ranked job matches\n"
            "• **Application stats** — progress report\n"
            "• **Pipeline status** — last run info\n"
            "• **Trigger pipeline** — run the job search now\n"
            "• **Market insights** — UAE market health and trends\n"
            "• **Application strategy** — personalized application approach\n"
            "• **Learning profile** — your preferences and inferred roles\n"
            "\nOr click Apply / Skip / Save on any job card."
        )
        ui_title = "Available Commands"
        commands = [
            "Show me today's best jobs",
            "Application stats",
            "Pipeline status",
            "Trigger pipeline",
            "Market insights",
            "Application strategy",
            "Learning profile",
        ]

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(
            type=AgentUIType.TEXT,
            title=ui_title,
            data={"commands": commands},
        ),
        tool_used="help",
        success=True,
    )


def _market_insights_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    """Builder for market insights (UAE-specific)."""
    health = data.get("market_health", {})
    status = health.get("status", "Unknown")
    health_score = health.get("health_score", 0)
    recommendations = data.get("recommendations", [])

    if lang == "ar":
        message = (
            f"صحة السوق: **{status}** (النقاط: {health_score}/100). "
            f"{recommendations[0] if recommendations else 'لا توجد توصيات محددة.'}"
        )
        view_label = "اعرض الاستراتيجية"
    else:
        message = (
            f"Market health: **{status}** (score: {health_score}/100). "
            f"{recommendations[0] if recommendations else 'No specific recommendations.'}"
        )
        view_label = "View Strategy"

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.TEXT, data=data),
        actions=[
            AgentAction(
                type="show_strategy",
                label=view_label,
                style=ActionStyle.SECONDARY,
            )
        ],
        tool_used=result.tool_name,
        success=True,
    )


def _strategy_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    """Builder for application strategy."""
    strategy = data.get("strategy", {})
    approach = strategy.get("approach", "Standard")
    tips = data.get("tips", [])

    if lang == "ar":
        message = f"أسلوب التقديم الموصى به لك: **{approach}**."
        if tips:
            message += f" أهم النصائح: {', '.join(tips[:3])}"
        view_label = "اعرض رؤى السوق"
    else:
        message = f"Your recommended application approach: **{approach}**."
        if tips:
            message += f" Key tips: {', '.join(tips[:3])}"
        view_label = "View Market Insights"

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.TEXT, data=data),
        actions=[
            AgentAction(
                type="show_market_insights",
                label=view_label,
                style=ActionStyle.SECONDARY,
            )
        ],
        tool_used=result.tool_name,
        success=True,
    )


def _learning_profile_response(result: ToolExecutionResult, data: Dict[str, Any], lang: str = "en") -> AgentUIResponse:
    """Builder for learning profile (user preferences)."""
    role_preferences = data.get("role_preferences", {})
    top_roles = list(role_preferences.items())[:3] if role_preferences else []
    skill_confidence = data.get("skill_confidence", {})

    if lang == "ar":
        message = f"أبديت اهتماماً بـ **{len(role_preferences)}** دور وظيفي."
        if top_roles:
            roles_str = ", ".join([f"{role} ({score:.1f})" for role, score in top_roles])
            message += f" أعلى اهتماماتك: {roles_str}"
        if skill_confidence:
            top_skills = sorted(skill_confidence.items(), key=lambda x: x[1], reverse=True)[:3]
            skills_str = ", ".join([skill for skill, _ in top_skills])
            message += f". أقوى مهاراتك: {skills_str}"
        update_label = "حدّث التفضيلات"
    else:
        message = f"You've shown interest in **{len(role_preferences)}** roles."
        if top_roles:
            roles_str = ", ".join([f"{role} ({score:.1f})" for role, score in top_roles])
            message += f" Top interests: {roles_str}"
        if skill_confidence:
            top_skills = sorted(skill_confidence.items(), key=lambda x: x[1], reverse=True)[:3]
            skills_str = ", ".join([skill for skill, _ in top_skills])
            message += f". Strong skills: {skills_str}"
        update_label = "Update Preferences"

    return AgentUIResponse(
        message=message,
        ui=AgentUIComponent(type=AgentUIType.TEXT, data=data),
        actions=[
            AgentAction(
                type="update_preferences",
                label=update_label,
                style=ActionStyle.SECONDARY,
            )
        ],
        tool_used=result.tool_name,
        success=True,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_title(action: Optional[AgentAction]) -> str:
    if action and action.job:
        return action.job.get("title") or "Unknown job"
    return "Unknown job"


def _job_company(action: Optional[AgentAction]) -> str:
    if action and action.job:
        return action.job.get("company") or "Unknown company"
    return "Unknown company"


def _deterministic_action_id(action_type: str, job: Dict[str, Any]) -> str:
    """
    SHA-256[:12] of "type:link".
    The same action on the same job always produces the same action_id,
    enabling idempotency checks in the audit repository.

    Fallback to composite key if link is missing to prevent collisions.
    """
    link = (job.get("link") or "").strip()
    # Use composite key if link is empty to prevent collisions
    if not link:
        link = f"{job.get('id', '')}:{job.get('title', '')}:{job.get('company', '')}"
    key = f"{action_type}:{link}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]
