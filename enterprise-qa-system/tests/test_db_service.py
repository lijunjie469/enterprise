"""Tests for database query service."""
import pytest
from app.services.db_service import DBService, DBSecurityError, ALLOWED_TABLES


class TestDBService:
    def test_get_employee_by_name(self, db):
        emp = db.get_employee_by_name("张三")
        assert emp is not None
        assert emp["employee_id"] == "EMP-001"
        assert emp["department"] == "研发部"
        assert emp["level"] == "P6"
        assert emp["email"] == "zhangsan@company.com"

    def test_get_employee_not_found(self, db):
        emp = db.get_employee_by_name("不存在的员工")
        assert emp is None

    def test_get_employee_by_id(self, db):
        emp = db.get_employee_by_id("EMP-999")
        assert emp is None

        emp = db.get_employee_by_id("EMP-001")
        assert emp["name"] == "张三"

    def test_get_employees_by_department(self, db):
        emps = db.get_employees_by_department("研发部")
        assert len(emps) == 4  # 张三, 李四, 钱七, 周九
        names = {e["name"] for e in emps}
        assert names == {"张三", "李四", "钱七", "周九"}

    def test_get_employee_count_by_department(self, db):
        assert db.get_employee_count_by_department("研发部") == 4
        assert db.get_employee_count_by_department("产品部") == 3
        assert db.get_employee_count_by_department("市场部") == 1

    def test_get_manager(self, db):
        mgr = db.get_employee_manager_name("EMP-002")
        assert mgr == "CEO"

    def test_get_projects_by_employee(self, db):
        projects = db.get_projects_by_employee("EMP-001")
        assert len(projects) == 4
        roles = {p["role"] for p in projects}
        assert "lead" in roles
        assert "core" in roles
        assert "contributor" in roles

    def test_get_attendance_by_month(self, db):
        records = db.get_attendance_by_employee_month("EMP-001", 2026, 2)
        assert len(records) > 0
        late = [r for r in records if r["status"] == "late"]
        assert len(late) == 2  # 张三2月迟到2次

    def test_get_performance(self, db):
        perf = db.get_performance_by_employee("EMP-001")
        assert len(perf) == 4
        for p in perf:
            assert p["year"] == 2025

    def test_get_performance_avg(self, db):
        avg = db.get_performance_avg("EMP-001")
        assert avg is not None
        assert abs(avg - 89.25) < 0.1

        avg2 = db.get_performance_avg("EMP-003")
        assert avg2 is not None
        assert abs(avg2 - 80.0) < 0.1

    def test_count_active_projects(self, db):
        projects = db.execute_query(
            "SELECT * FROM projects WHERE status = 'active'"
        )
        assert len(projects) == 2  # PRJ-001, PRJ-003

    def test_sql_injection_blocked(self, db):
        with pytest.raises(DBSecurityError):
            db.execute_query("DROP TABLE employees")

        with pytest.raises(DBSecurityError):
            db.execute_query("DELETE FROM employees WHERE 1=1")

        with pytest.raises(DBSecurityError):
            db.execute_query("INSERT INTO employees VALUES ('x','y')")

    def test_parameterized_query_safe(self, db):
        results = db.execute_query(
            "SELECT name FROM employees WHERE employee_id = ?",
            ("EMP-001",),
        )
        assert len(results) == 1
        assert results[0]["name"] == "张三"

    def test_get_table_info(self, db):
        info = db.get_table_info()
        assert "employees" in info
        assert "projects" in info
        assert "employee_id" in info["employees"]

    def test_fuzzy_name_search(self, db):
        results = db.search_employee_by_name_fuzzy("张")
        assert len(results) >= 1
        assert any(r["name"] == "张三" for r in results)

    def test_project_member_count(self, db):
        count = db.get_project_member_count("EMP-001")
        assert count == 4

        count2 = db.get_project_member_count("EMP-003")
        assert count2 == 1
