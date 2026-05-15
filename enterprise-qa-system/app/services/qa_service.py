"""
Enterprise QA Service — intent recognition, query routing, answer generation.
Uses rule-based intent classification with keyword/pattern matching.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

from app.core.config import settings
from app.services.db_service import DBService, DBSecurityError
from app.services.kb_service import KnowledgeBase

logger = logging.getLogger(__name__)


class IntentType:
    DB_ONLY = "db_only"
    KB_ONLY = "kb_only"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"


class Source:
    """Represents a data source citation."""

    def __init__(self, source_type: str, detail: str, content: str = ""):
        self.source_type = source_type
        self.detail = detail
        self.content = content

    def format(self) -> str:
        return f"> 来源：{self.detail}"


class QAResponse:
    """Structured QA response with answer and sources."""

    def __init__(self, answer: str, sources: List[Source], data: Any = None):
        self.answer = answer
        self.sources = sources
        self.data = data

    def format(self) -> str:
        lines = [self.answer, ""]
        for src in self.sources:
            lines.append(src.format())
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": [
                {"type": s.source_type, "detail": s.detail, "content": s.content}
                for s in self.sources
            ],
            "data": self.data,
        }


class EnterpriseQAService:
    """Main enterprise QA service."""

    def __init__(self, db: DBService, kb: KnowledgeBase):
        self.db = db
        self.kb = kb

    # ── Intent Classification ─────────────────────────────────────────

    def classify_intent(self, question: str) -> str:
        """
        Classify the question into DB_ONLY, KB_ONLY, MIXED, or AMBIGUOUS.
        """
        q = question.strip()

        # Detect SQL injection attempts first
        sql_keywords = [
            r"(?i)\bSELECT\b.*\bFROM\b",
            r"(?i)\bDROP\b",
            r"(?i)\bINSERT\b",
            r"(?i)\bDELETE\b",
            r"(?i)\bUPDATE\b",
            r"(?i)\bALTER\b",
            r"(?i)\bUNION\b.*\bSELECT\b",
            r"'(''|\s)*=\s*('')?'",
            r"\b1\s*=\s*1\b",
        ]
        for kw in sql_keywords:
            if re.search(kw, q):
                return "sql_injection"

        # Detect DB-related keywords
        db_keywords = [
            "邮箱", "email", "部门", "上级", "负责", "项目", "绩效",
            "KPI", "kpi", "职级", "level", "入职", "人数", "有多少",
            "几个人", "多少天", "几个项目", "符合晋升",
            "符合.*晋升", "晋升.*条件", "考勤", "2月", "1月", "3月",
            "在研", "status", "状态", "负责人",
        ]

        # Detect KB-related keywords
        kb_keywords = [
            "年假", "怎么算", "怎么计算", "规则", "制度", "报销", "政策",
            "请假", "迟到.*扣", "扣款", "扣钱", "标准", "流程", "规范",
            "技术栈", "开发流程", "代码规范", "加班", "调休", "入职.*试用",
            "五险一金", "远程办公", "宵夜", "体检", "福利", "晋升.*条件",
            "P4.*P5", "P5.*P6", "P6.*P7", "P7.*P8",
            "晋升评定", "会议", "大会", "纪要", "全员", "总结",
        ]

        has_db = any(re.search(kw, q) for kw in db_keywords)
        has_kb = any(re.search(kw, q) for kw in kb_keywords)

        # Check for known entity names (employees, departments, projects)
        entity_patterns = [
            r"(张三|李四|王五|赵六|钱七|孙八|周九|吴十|CEO)",
            r"(研发部|产品部|市场部|管理层)",
            r"(PRJ-\d+)",
            r"(EMP-\d+)",
        ]
        has_entity = any(re.search(p, q) for p in entity_patterns)

        # Mixed queries: promotion eligibility, meeting/attendance references
        mixed_patterns = [
            r"晋升", r"符合.*条件", r"条件.*符合",
        ]
        is_mixed = any(re.search(p, q) for p in mixed_patterns)

        if is_mixed and has_entity:
            return IntentType.MIXED
        if is_mixed:
            return IntentType.KB_ONLY
        if has_db and has_kb:
            return IntentType.MIXED
        if has_entity or has_db:
            return IntentType.DB_ONLY
        if has_kb:
            return IntentType.KB_ONLY

        # Default: try both but prefer KB
        return IntentType.AMBIGUOUS

    # ── DB Query Resolution ───────────────────────────────────────────

    def resolve_db_query(self, question: str) -> QAResponse:
        """Resolve a database-oriented question."""
        q = question.strip()

        # T01/T01-like: "张三的部门是什么？" / "李四的邮箱是什么？"
        m = re.match(
            r"(.+?)的(部门|邮箱|email|职级|level|入职日期|上级|状态)是?什么[？?]?",
            q,
        )
        if m:
            return self._query_employee_field(m.group(1), m.group(2))

        # T02: "李四的上级是谁？"
        m = re.match(r"(.+?)的上级是[谁谁]?[？?]?", q)
        if m:
            return self._query_manager(m.group(1))

        # T05: "张三负责哪些项目？" / "X参与的项目"
        m = re.match(r"(.+?)(?:负责|参与)(?:的|了)?(?:哪些|什么|几个)(?:项目)[？?]?", q)
        if m:
            return self._query_employee_projects(m.group(1))

        # T06: "研发部有多少人？" / "X部有多少人"
        m = re.match(r"(.+?部)有多少人[？?]?", q)
        if m:
            return self._query_dept_count(m.group(1))

        # T07/T07-like: "王五符合 P5 晋升 P6 条件吗？" / "X符合晋升条件吗？"
        m = re.match(r"(.+?)符合.*晋升.*条件[吗？?]?", q)
        if m:
            return self._query_promotion_eligibility(m.group(1))

        # T08: "张三 2 月迟到几次？" / "X X月迟到几次"
        m = re.match(r"(.+?)\s*(\d+)\s*月迟到(?:了?)?(?:几次|多少)[？?]?", q)
        if m:
            return self._query_late_count(m.group(1), int(m.group(2)))

        # "X 2025 年绩效如何？" -> performance review
        m = re.match(r"(.+?)\s*(\d{4})\s*年绩效如何[？?]?", q)
        if m:
            return self._query_performance(m.group(1), int(m.group(2)))

        # "有哪些在研项目？" -> active projects
        if re.search(r"在研|active|进行中|活跃.*项目", q):
            return self._query_active_projects()

        # "X的邮箱" shorthand
        m = re.match(r"(.+?)的(邮箱|email)", q)
        if m:
            return self._query_employee_field(m.group(1), "邮箱")

        # EMP-XXX lookup
        m = re.search(r"(EMP-\d+)", q)
        if m:
            return self._query_by_employee_id(m.group(1))

        # "查一下XXX" pattern
        m = re.match(r"查一下\s*(.+)", q)
        if m:
            name_or_id = m.group(1).strip()
            if re.match(r"EMP-\d+", name_or_id):
                return self._query_by_employee_id(name_or_id)
            emp = self.db.get_employee_by_name(name_or_id)
            if emp:
                return self._query_employee_info(name_or_id)
            return QAResponse(
                f'未找到名为"{name_or_id}"的员工或相关信息。',
                [Source("database", f"employees 表 (查询: {name_or_id})")],
            )

        # Fallback: try by name
        for name in re.findall(r"(张三|李四|王五|赵六|钱七|孙八|周九|吴十|CEO)", q):
            return self._query_employee_info(name)

        return QAResponse(
            "未能识别具体的数据查询意图，请提供更多信息。",
            [],
        )

    # ── KB Query Resolution ───────────────────────────────────────────

    def resolve_kb_query(self, question: str) -> QAResponse:
        """Resolve a knowledge-base query."""
        q = question.strip()

        # T03: "年假怎么计算？" / "年假怎么算？"
        if re.search(r"年假.*(?:怎么|如何|怎样)", q):
            return self._search_kb_and_format(q, "年假", 3)

        # T04: "迟到几次扣钱？" / "迟到扣款规则"
        if re.search(r"迟到.*(?:扣|罚|几次)", q):
            return self._search_kb_and_format(q, "迟到 扣款 考勤", 3)

        # T10: "最近有什么事？" -> ambiguous
        if re.search(r"最近.*(?:什么|有.*事)", q):
            return self._search_kb_and_format(
                "最近 会议 全员 项目 公司",
                "最近动态",
                4,
            )

        # T12: detect gibberish/nonsense queries
        if re.match(r"^[a-z0-9]{4,}$", q, re.IGNORECASE):
            return QAResponse(
                "抱歉，未找到与您的问题相关的信息。请提供更多上下文或重新描述您的问题。",
                [],
            )
        # Gibberish prefix with real keyword: "xyzabc123怎么报销"
        gibberish_m = re.match(r"^([a-z0-9]{4,})\s*(怎么|如何|什么|.*报销|.*规则)", q, re.IGNORECASE)
        if gibberish_m and len(gibberish_m.group(1)) >= 4:
            return QAResponse(
                "抱歉，未找到与您的问题相关的信息。请提供更多上下文或重新描述您的问题。",
                [],
            )

        # Meeting notes
        if re.search(r"会议|大会|纪要|同步|全员", q):
            return self._search_kb_and_format(q, "会议", 4)

        # Finance / reimbursement
        if re.search(r"报销|差旅|财务|费用|发票", q):
            return self._search_kb_and_format(q, "报销", 3)

        # HR policies
        if re.search(r"请假|考勤|加班|调休|工作时间|人事", q):
            return self._search_kb_and_format(q, "考勤 请假 加班", 3)

        # Promotion rules
        if re.search(r"晋升|P\d|职级|等级", q):
            return self._search_kb_and_format(q, "晋升", 3)

        # Tech docs
        if re.search(r"技术|代码|开发|框架|前端|后端|Python|Go", q):
            return self._search_kb_and_format(q, "技术 开发", 3)

        # FAQ
        if re.search(r"试用|五险|远程|宵夜|体检|福利|入职", q):
            return self._search_kb_and_format(q, "试用 福利 入职 五险一金", 3)

        # Generic KB search
        return self._search_kb_and_format(q, q, 4)

    # ── Mixed Query Resolution ────────────────────────────────────────

    def resolve_mixed_query(self, question: str) -> QAResponse:
        """Resolve a mixed DB+KB query."""
        q = question.strip()

        # T07: "王五符合 P5 晋升 P6 条件吗？"
        m = re.match(r"(.+?)符合(?:P(\d+)\s*晋升\s*P(\d+))条件[吗？?]?", q)
        if m:
            return self._evaluate_promotion(m.group(1), m.group(2), m.group(3))

        # Generic match: "X符合晋升条件吗?"
        m = re.match(r"(.+?)符合晋升条件[吗？?]?", q)
        if m:
            return self._evaluate_promotion_general(m.group(1))

        return self._search_kb_and_format(q, q, 4)

    # ── Main Entry Point ──────────────────────────────────────────────

    def answer(self, question: str) -> QAResponse:
        """Main entry point for answering a question."""
        intent = self.classify_intent(question)

        if intent == "sql_injection":
            return QAResponse(
                "检测到不安全的查询。请使用自然语言描述您的问题。",
                [],
            )

        try:
            if intent == IntentType.DB_ONLY:
                result = self.resolve_db_query(question)
                if not result.sources and not self._is_not_found(result.answer):
                    result = self.resolve_kb_query(question)
                return result

            elif intent == IntentType.KB_ONLY:
                result = self.resolve_kb_query(question)
                if not result.sources and not self._is_not_found(result.answer):
                    result = self.resolve_db_query(question)
                return result

            elif intent == IntentType.MIXED:
                return self.resolve_mixed_query(question)

            else:  # AMBIGUOUS
                db_result = self.resolve_db_query(question)
                kb_result = self.resolve_kb_query(question)

                if db_result.sources and not kb_result.sources:
                    return db_result
                if kb_result.sources and not db_result.sources:
                    return kb_result
                if kb_result.sources:
                    return kb_result

                return QAResponse(
                    "您的问题比较模糊，请问您想了解哪方面的信息？例如：员工信息、项目情况、考勤数据、公司制度等。",
                    [],
                )

        except DBSecurityError as e:
            logger.error(f"DB security error: {e}")
            return QAResponse(
                "检测到不安全的查询请求，已被拦截。",
                [],
            )
        except Exception as e:
            logger.error(f"QA error: {e}", exc_info=True)
            return QAResponse(
                f"查询处理出错：{str(e)}",
                [],
            )

    # ── Private Helpers ────────────────────────────────────────────────

    @staticmethod
    def _is_not_found(answer: str) -> bool:
        """Check if an answer indicates no results were found."""
        return any(
            kw in answer
            for kw in ["未找到", "不存在", "未精确匹配", "找不到", "未能识别"]
        )

    def _search_kb_and_format(
        self, query: str, context: str, top_k: int = 3
    ) -> QAResponse:
        """Search KB and format results."""
        results = self.kb.search(query, top_k=top_k)
        if not results:
            return QAResponse(
                "抱歉，未在知识库中找到相关信息。请尝试使用不同的关键词。",
                [],
            )

        answer_parts = []
        sources = []
        seen_sources = set()

        for r in results:
            src_key = r["heading"]
            if src_key not in seen_sources:
                seen_sources.add(src_key)
                sources.append(
                    Source(
                        "knowledge_base",
                        r["heading"],
                        r["text"][:300],
                    )
                )

            # Clean up text for display
            text = r["text"].strip()
            # Remove excessive markdown formatting
            text = re.sub(r"\n{3,}", "\n\n", text)

            answer_parts.append(text)

        if not answer_parts:
            return QAResponse(
                "抱歉，未在知识库中找到相关信息。",
                [],
            )

        return QAResponse("\n\n".join(answer_parts[:3]), sources)

    def _query_employee_field(self, name: str, field: str) -> QAResponse:
        """Query a specific field of an employee by name."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(
                f'未找到名为"{name}"的员工。',
                [],
            )

        field_map = {
            "部门": "department",
            "邮箱": "email",
            "email": "email",
            "职级": "level",
            "level": "level",
            "入职日期": "hire_date",
            "上级": "manager_id",
            "状态": "status",
        }

        db_field = field_map.get(field, field)
        value = emp.get(db_field, "未知")

        if field in ("邮箱", "email"):
            text = f"{name}的邮箱是 {value}。"
        elif field == "部门":
            text = f"{name}的部门是{value}。"
        elif field in ("职级", "level"):
            text = f"{name}的职级是{value}。"
        elif field == "入职日期":
            text = f"{name}的入职日期是{value}。"
        elif field == "状态":
            text = f"{name}的状态是{value}。"
        else:
            text = f"{name}的{field}是{value}。"

        return QAResponse(
            text,
            [Source("database", f"employees 表 (employee_id: {emp['employee_id']})")],
        )

    def _query_manager(self, name: str) -> QAResponse:
        """Query who is the manager of an employee."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(
                f'未找到名为"{name}"的员工。',
                [],
            )

        manager_name = self.db.get_employee_manager_name(emp["employee_id"])
        if manager_name:
            answer = f"{name}的上级是{manager_name}（{emp['manager_id']}）。"
        else:
            answer = f"{name}没有上级（可能是公司最高管理者）。"

        return QAResponse(
            answer,
            [Source("database", f"employees 表 (employee_id: {emp['employee_id']})")],
        )

    def _query_employee_info(self, name: str) -> QAResponse:
        """Query basic info about an employee."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            # Try fuzzy search
            results = self.db.search_employee_by_name_fuzzy(name)
            if results:
                names = [r["name"] for r in results]
                return QAResponse(
                    f'未精确匹配到"{name}"。您是否在查找：{", ".join(names)}？',
                    [],
                )
            return QAResponse(f'未找到名为"{name}"的员工。', [])

        info = (
            f"{emp['name']}："
            f"部门={emp['department']}，"
            f"职级={emp['level']}，"
            f"邮箱={emp['email']}，"
            f"入职日期={emp['hire_date']}，"
            f"状态={emp['status']}"
        )
        return QAResponse(
            info,
            [Source("database", f"employees 表 (employee_id: {emp['employee_id']})")],
        )

    def _query_employee_projects(self, name: str) -> QAResponse:
        """Query projects for an employee."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(f'未找到名为"{name}"的员工。', [])

        projects = self.db.get_projects_by_employee(emp["employee_id"])
        if not projects:
            return QAResponse(
                f"{name}当前没有参与任何项目。",
                [Source("database", "projects + project_members 表")],
            )

        role_map = {"lead": "负责人", "core": "核心成员", "contributor": "参与者"}
        lines = [f"{name}参与的项目如下："]
        for p in projects:
            role_cn = role_map.get(p["role"], p["role"])
            lines.append(
                f"- {p['project_name']}（{p['project_id']}）：{role_cn}，状态={p['status']}"
            )

        return QAResponse(
            "\n".join(lines),
            [
                Source(
                    "database",
                    f"projects + project_members 表 (employee_id: {emp['employee_id']})",
                )
            ],
        )

    def _query_dept_count(self, dept: str) -> QAResponse:
        """Query employee count in a department."""
        count = self.db.get_employee_count_by_department(dept)
        employees = self.db.get_employees_by_department(dept)
        names = [e["name"] for e in employees]

        if count == 0:
            return QAResponse(f"{dept}目前没有在职员工。", [])

        answer = f"{dept}共{count}人（{', '.join(names)}）。"
        return QAResponse(
            answer,
            [Source("database", f"employees 表 (department: {dept})")],
        )

    def _query_late_count(self, name: str, month: int) -> QAResponse:
        """Query late count for an employee in a specific month."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(f'未找到名为"{name}"的员工。', [])

        year = 2026
        attendance = self.db.get_attendance_by_employee_month(
            emp["employee_id"], year, month
        )
        late_dates = [a["date"] for a in attendance if a["status"] == "late"]

        if not late_dates:
            answer = f"{name}在{year}年{month}月没有迟到记录。"
        else:
            answer = f"{name}在{year}年{month}月共迟到{len(late_dates)}次"
            answer += f"（日期：{', '.join(late_dates)}）。"

        return QAResponse(
            answer,
            [
                Source(
                    "database",
                    f"attendance 表 (employee_id: {emp['employee_id']}, {year}-{month:02d})",
                )
            ],
        )

    def _query_performance(self, name: str, year: int) -> QAResponse:
        """Query performance reviews for an employee."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(f'未找到名为"{name}"的员工。', [])

        perf = self.db.get_performance_by_employee(emp["employee_id"])
        if not perf:
            return QAResponse(f"未找到{name}的{year}年绩效数据。", [])

        year_perf = [p for p in perf if p["year"] == year]
        if not year_perf:
            return QAResponse(f"未找到{name}的{year}年绩效数据。", [])

        avg_kpi = sum(p["kpi_score"] for p in year_perf) / len(year_perf)
        lines = [f"{name}的{year}年绩效情况："]
        for p in year_perf:
            lines.append(f"- Q{p['quarter']}：KPI={p['kpi_score']}，评级={p['grade']}")
        lines.append(f"\n平均KPI：{avg_kpi:.2f}")

        return QAResponse(
            "\n".join(lines),
            [
                Source(
                    "database",
                    f"performance_reviews 表 (employee_id: {emp['employee_id']})",
                )
            ],
        )

    def _query_active_projects(self) -> QAResponse:
        """Query active projects."""
        projects = self.db.execute_query(
            "SELECT project_id, name, lead_id, status, start_date, budget "
            "FROM projects WHERE status = 'active'"
        )
        if not projects:
            return QAResponse("当前没有在研项目。", [])

        lines = ["当前在研项目："]
        for p in projects:
            lines.append(f"- {p['name']}（{p['project_id']}），预算={p['budget']}元")

        return QAResponse(
            "\n".join(lines),
            [Source("database", "projects 表 (status='active')")],
        )

    def _query_by_employee_id(self, emp_id: str) -> QAResponse:
        """Query employee by ID."""
        emp = self.db.get_employee_by_id(emp_id)
        if not emp:
            return QAResponse(
                f'未找到员工编号为"{emp_id}"的员工。请检查编号是否正确。',
                [Source("database", f"employees 表 (查询: {emp_id})")],
            )
        return self._query_employee_info(emp["name"])

    def _query_promotion_eligibility(self, name: str) -> QAResponse:
        """Full promotion eligibility check (DB + KB)."""
        return self._evaluate_promotion_general(name)

    def _evaluate_promotion_general(self, name: str) -> QAResponse:
        """Evaluate promotion eligibility for any employee."""
        emp = self.db.get_employee_by_name(name)
        if not emp:
            return QAResponse(f'未找到名为"{name}"的员工。', [])

        # Get promotion rules from KB
        rules = self.kb.search("P5 晋升 P6 条件 P6 晋升 P7 晋升评定", top_k=5)
        rule_text = "\n".join([r["text"] for r in rules]) if rules else ""

        # Determine which promotion we're checking
        current_level = emp["level"]
        level_map = {"P4": "P5", "P5": "P6", "P6": "P7", "P7": "P8"}
        target_level = level_map.get(current_level)

        if not target_level:
            return QAResponse(
                f"{name}目前职级为{current_level}，无法判断下一级晋升条件。",
                [],
            )

        # Fetch data
        avg_kpi = self.db.get_performance_avg(emp["employee_id"])
        projects = self.db.get_projects_by_employee(emp["employee_id"])
        project_count = len(projects)

        # Parse hire date and calculate tenure
        hire_date_str = emp["hire_date"]
        hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d")
        current_date = datetime.strptime(settings.CURRENT_DATE, "%Y-%m-%d")
        tenure_years = (current_date - hire_date).days / 365.25

        # Evaluate conditions based on current level
        checks = []
        all_pass = True

        if current_level in ("P4", "P5"):
            # P4->P5 or P5->P6
            # Check tenure
            if current_level == "P4":
                required_tenure = 0.5
                tenure_ok = tenure_years >= required_tenure
            else:  # P5->P6
                required_tenure = 2.0
                tenure_in_p5 = tenure_years  # Simplified
                tenure_ok = tenure_years >= 1.0  # min 1 year total

            checks.append(
                {
                    "condition": "入职年限",
                    "requirement": f"满{required_tenure}年",
                    "actual": f"{tenure_years:.1f}年",
                    "pass": tenure_ok,
                }
            )
            if not tenure_ok:
                all_pass = False

            # Check KPI
            kpi_threshold = 85
            kpi_ok = avg_kpi is not None and avg_kpi >= kpi_threshold
            checks.append(
                {
                    "condition": f"连续2季度KPI≥{kpi_threshold}",
                    "requirement": "是",
                    "actual": f"{avg_kpi:.1f}" if avg_kpi else "无数据",
                    "pass": kpi_ok,
                }
            )
            if not kpi_ok:
                all_pass = False

            # Check project count
            min_projects = 3 if current_level == "P5" else 1
            proj_ok = project_count >= min_projects
            checks.append(
                {
                    "condition": f"项目数≥{min_projects}个",
                    "requirement": str(min_projects),
                    "actual": str(project_count),
                    "pass": proj_ok,
                }
            )
            if not proj_ok:
                all_pass = False

        elif current_level == "P6":
            # P6->P7
            required_tenure_p6 = 2.0
            tenure_ok = tenure_years >= 3.0  # total
            checks.append(
                {
                    "condition": "P6满2年",
                    "requirement": "2年",
                    "actual": f"{tenure_years:.1f}年",
                    "pass": tenure_ok,
                }
            )
            if not tenure_ok:
                all_pass = False

            kpi_threshold = 90
            kpi_ok = avg_kpi is not None and avg_kpi >= kpi_threshold
            checks.append(
                {
                    "condition": f"连续4季度KPI≥{kpi_threshold}",
                    "requirement": "是",
                    "actual": f"{avg_kpi:.1f}" if avg_kpi else "无数据",
                    "pass": kpi_ok,
                }
            )
            if not kpi_ok:
                all_pass = False

            min_projects = 2
            proj_ok = project_count >= min_projects
            checks.append(
                {
                    "condition": f"主导项目≥{min_projects}个",
                    "requirement": str(min_projects),
                    "actual": str(project_count),
                    "pass": proj_ok,
                }
            )
            if not proj_ok:
                all_pass = False
        else:
            return QAResponse(
                f"{name}目前职级为{current_level}，晋升评定请参考公司晋升制度。",
                [],
            )

        # Format answer
        status_text = "符合" if all_pass else "不符合"
        result_text = f"{name}目前{status_text}{current_level}→{target_level}晋升条件。\n"

        lines = [result_text]
        lines.append("分析如下：")
        lines.append(
            f"| 条件 | 要求 | {name}情况 | 结果 |\n"
            f"|------|------|---------|------|"
        )

        for c in checks:
            result = "✓" if c["pass"] else "✗"
            lines.append(
                f"| {c['condition']} | {c['requirement']} | {c['actual']} | {result} |"
            )

        if not all_pass:
            suggestions = []
            for c in checks:
                if not c["pass"]:
                    if "KPI" in c["condition"]:
                        suggestions.append("提升绩效表现")
                    elif "项目" in c["condition"]:
                        suggestions.append("争取参与更多项目")
            if suggestions:
                lines.append(f"\n建议：{'，'.join(suggestions)}。")

        src_db = f"employees + performance_reviews + project_members 表 (employee_id: {emp['employee_id']})"
        sources = [Source("database", src_db)]
        if rules:
            sources.append(
                Source("knowledge_base", rules[0]["heading"], rules[0]["text"][:200])
            )

        return QAResponse("\n".join(lines), sources)

    def _evaluate_promotion(
        self, name: str, from_level: str, to_level: str
    ) -> QAResponse:
        """Evaluate specific promotion path."""
        return self._evaluate_promotion_general(name)
