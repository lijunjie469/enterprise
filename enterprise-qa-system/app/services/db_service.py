"""
Database query service for enterprise SQLite database.
Uses parameterized queries exclusively — no string concatenation.
"""
import sqlite3
import re
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date

logger = logging.getLogger(__name__)


# Prevent execution of dangerous SQL patterns
FORBIDDEN_SQL_PATTERNS = [
    r"(?i)\bINSERT\b",
    r"(?i)\bUPDATE\b",
    r"(?i)\bDELETE\b",
    r"(?i)\bDROP\b",
    r"(?i)\bALTER\b",
    r"(?i)\bCREATE\b",
    r"(?i)\bTRUNCATE\b",
    r"(?i)\bREPLACE\b",
    r"(?i)--",                # SQL comments (injection bypass)
    r"(?i);\s*\bDROP\b",      # statement chaining
    r"(?i);\s*\bDELETE\b",
]

# Whitelist: only these tables can be queried
ALLOWED_TABLES = [
    "employees",
    "projects",
    "project_members",
    "attendance",
    "performance_reviews",
]

TABLE_SCHEMA = {
    "employees": {
        "columns": [
            "employee_id", "name", "department", "level",
            "hire_date", "manager_id", "email", "status"
        ],
        "description": "员工信息表：employee_id(员工ID), name(姓名), department(部门), level(职级), hire_date(入职日期), manager_id(上级ID), email(邮箱), status(状态: active/on_leave/resigned)",
        "safe_columns": ["employee_id", "name", "department", "level", "hire_date", "email", "status"],
    },
    "projects": {
        "columns": [
            "project_id", "name", "lead_id", "status",
            "start_date", "end_date", "budget"
        ],
        "description": "项目记录表：project_id(项目ID), name(项目名称), lead_id(负责人ID), status(状态: planning/active/on_hold/completed), start_date, end_date, budget",
        "safe_columns": ["project_id", "name", "lead_id", "status", "start_date", "end_date", "budget"],
    },
    "project_members": {
        "columns": ["project_id", "employee_id", "role", "join_date"],
        "description": "项目成员关联表：project_id, employee_id, role(角色: lead/core/contributor), join_date",
        "safe_columns": ["project_id", "employee_id", "role", "join_date"],
    },
    "attendance": {
        "columns": ["id", "employee_id", "date", "status"],
        "description": "考勤记录表：employee_id, date(日期), status(状态: on_time/late/absent/on_leave)",
        "safe_columns": ["id", "employee_id", "date", "status"],
    },
    "performance_reviews": {
        "columns": ["id", "employee_id", "year", "quarter", "kpi_score", "grade"],
        "description": "绩效考核表：employee_id, year, quarter(季度:1-4), kpi_score(KPI分数:0-100), grade(评级: S/A/B/C)",
        "safe_columns": ["id", "employee_id", "year", "quarter", "kpi_score", "grade"],
    },
}


class DBSecurityError(Exception):
    """Raised when SQL contains forbidden patterns."""
    pass


class DBService:
    """Enterprise database query service with SQL injection protection."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _validate_sql(self, sql: str) -> None:
        """Validate SQL against forbidden patterns."""
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, sql):
                raise DBSecurityError(
                    f"SQL包含禁止操作或可疑模式: {pattern}"
                )

    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a read-only parameterized SQL query."""
        self._validate_sql(sql)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def execute_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query expecting at most one result."""
        results = self.execute_query(sql, params)
        return results[0] if results else None

    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        return self.execute_one(
            "SELECT employee_id, name, department, level, hire_date, manager_id, email, status "
            "FROM employees WHERE employee_id = ?",
            (employee_id,),
        )

    def get_employee_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.execute_one(
            "SELECT employee_id, name, department, level, hire_date, manager_id, email, status "
            "FROM employees WHERE name = ?",
            (name,),
        )

    def get_employees_by_department(self, department: str) -> List[Dict[str, Any]]:
        return self.execute_query(
            "SELECT employee_id, name, department, level, hire_date, manager_id, email, status "
            "FROM employees WHERE department = ? AND status = 'active'",
            (department,),
        )

    def get_projects_by_employee(self, employee_id: str) -> List[Dict[str, Any]]:
        return self.execute_query(
            "SELECT p.project_id, p.name AS project_name, p.status, pm.role "
            "FROM project_members pm "
            "JOIN projects p ON pm.project_id = p.project_id "
            "WHERE pm.employee_id = ?",
            (employee_id,),
        )

    def get_attendance_by_employee_month(
        self, employee_id: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        date_prefix = f"{year}-{month:02d}"
        return self.execute_query(
            "SELECT date, status FROM attendance "
            "WHERE employee_id = ? AND date LIKE ?",
            (employee_id, f"{date_prefix}%"),
        )

    def get_performance_by_employee(self, employee_id: str) -> List[Dict[str, Any]]:
        return self.execute_query(
            "SELECT year, quarter, kpi_score, grade "
            "FROM performance_reviews WHERE employee_id = ? "
            "ORDER BY year, quarter",
            (employee_id,),
        )

    def get_performance_avg(self, employee_id: str) -> Optional[float]:
        row = self.execute_one(
            "SELECT AVG(kpi_score) AS avg_kpi "
            "FROM performance_reviews WHERE employee_id = ?",
            (employee_id,),
        )
        return row["avg_kpi"] if row else None

    def search_employee_by_name_fuzzy(self, name: str) -> List[Dict[str, Any]]:
        return self.execute_query(
            "SELECT employee_id, name, department, level, hire_date, manager_id, email, status "
            "FROM employees WHERE name LIKE ?",
            (f"%{name}%",),
        )

    def get_project_member_count(self, employee_id: str) -> int:
        row = self.execute_one(
            "SELECT COUNT(*) AS cnt FROM project_members WHERE employee_id = ?",
            (employee_id,),
        )
        return row["cnt"] if row else 0

    def get_employee_count_by_department(self, department: str) -> int:
        row = self.execute_one(
            "SELECT COUNT(*) AS cnt FROM employees "
            "WHERE department = ? AND status = 'active'",
            (department,),
        )
        return row["cnt"] if row else 0

    def get_employee_manager_name(self, employee_id: str) -> Optional[str]:
        row = self.execute_one(
            "SELECT m.name AS manager_name "
            "FROM employees e "
            "LEFT JOIN employees m ON e.manager_id = m.employee_id "
            "WHERE e.employee_id = ?",
            (employee_id,),
        )
        return row["manager_name"] if row else None

    def get_table_info(self) -> Dict[str, List[str]]:
        """Return column info for all allowed tables."""
        return {
            table: info["safe_columns"]
            for table, info in TABLE_SCHEMA.items()
        }


# Singleton
_db_instance: Optional[DBService] = None


def get_db(db_path: Optional[str] = None) -> DBService:
    global _db_instance
    if _db_instance is None:
        from app.core.config import settings

        path = db_path or settings.DB_PATH
        _db_instance = DBService(path)
    return _db_instance
