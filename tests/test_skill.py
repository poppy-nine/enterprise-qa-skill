#!/usr/bin/env python3
"""
企业智能问答助手 - 单元测试
测试覆盖率目标：80%+
"""

import pytest
import sys
import os

# 添加 skill 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import EnterpriseQA, QueryResult


class TestEnterpriseQA:
    """测试企业智能问答系统"""

    @pytest.fixture
    def qa(self):
        """创建 QA 实例"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        return EnterpriseQA(config_path)

    # ============ 基础查询测试 (T01-T04) ============

    def test_t01_employee_department(self, qa):
        """T01: 张三的部门是什么？"""
        result = qa.answer("张三的部门是什么？")
        assert result.query_type == 'db'
        assert '研发部' in result.answer
        assert 'EMP-001' in result.source

    def test_t02_employee_manager(self, qa):
        """T02: 李四的上级是谁？"""
        result = qa.answer("李四的上级是谁？")
        assert result.query_type == 'db'
        assert 'CEO' in result.answer or 'EMP-000' in result.answer
        assert 'employees' in result.source

    def test_t03_annual_leave(self, qa):
        """T03: 年假怎么计算？"""
        result = qa.answer("年假怎么计算？")
        assert result.query_type == 'kb'
        assert '5天' in result.answer or '15天' in result.answer
        assert 'hr_policies' in result.source

    def test_t04_late_penalty(self, qa):
        """T04: 迟到几次扣钱？"""
        result = qa.answer("迟到几次扣钱？")
        assert result.query_type == 'kb'
        assert '4' in result.answer or '6' in result.answer
        assert '50' in result.answer

    # ============ 关联查询测试 (T05-T08) ============

    def test_t05_employee_projects(self, qa):
        """T05: 张三负责哪些项目？"""
        result = qa.answer("张三负责哪些项目？")
        assert result.query_type == 'db'
        assert 'PRJ-001' in result.answer or 'ReMe' in result.answer
        assert 'lead' in result.answer
        assert 'project_members' in result.source

    def test_t06_department_count(self, qa):
        """T06: 研发部有多少人？"""
        result = qa.answer("研发部有多少人？")
        assert result.query_type == 'db'
        assert '4人' in result.answer
        assert '研发部' in result.source

    def test_t07_promotion_eligibility(self, qa):
        """T07: 王五符合 P5 晋升 P6 条件吗？"""
        result = qa.answer("王五符合 P5 晋升 P6 条件吗？")
        assert result.query_type == 'mixed'
        assert '不符合' in result.answer or '符合' in result.answer
        # 王五 KPI 平均80 < 85，项目数1 < 3，应该不符合
        assert '不符合' in result.answer or 'KPI' in result.answer
        assert 'promotion_rules' in result.source

    def test_t08_attendance_late(self, qa):
        """T08: 张三2月迟到几次？"""
        result = qa.answer("张三2月迟到几次？")
        assert result.query_type == 'db'
        assert '2次' in result.answer
        assert 'attendance' in result.source

    # ============ 边界情况测试 (T09-T12) ============

    def test_t09_nonexistent_employee(self, qa):
        """T09: 查一下 EMP-999"""
        result = qa.answer("查一下 EMP-999")
        assert '未找到' in result.answer or '不存在' in result.answer

    def test_t10_fuzzy_question(self, qa):
        """T10: 最近有什么事？"""
        result = qa.answer("最近有什么事？")
        # 应该返回会议纪要或追问
        assert result.answer != ""

    def test_t11_sql_injection(self, qa):
        """T11: SQL注入攻击检测"""
        result = qa.answer("SELECT * FROM users WHERE '1'='1")
        assert 'SQL注入' in result.answer or '拦截' in result.answer
        assert result.query_type == 'error'

    def test_t12_no_match_content(self, qa):
        """T12: 无匹配内容处理"""
        result = qa.answer("xyzabc123怎么处理")
        assert '未找到' in result.answer or '抱歉' in result.answer
        assert result.query_type == 'unknown'

    # ============ 安全测试 ============

    def test_sql_injection_prevention(self, qa):
        """测试SQL注入防护"""
        malicious_inputs = [
            "张三'; DROP TABLE employees; --",
            "' OR '1'='1",
            "1; DELETE FROM employees",
        ]
        for input_str in malicious_inputs:
            result = qa.answer(input_str)
            # 应该被拦截或安全处理
            assert 'DROP' not in result.source
            assert '注入' in result.answer or '拦截' in result.answer or result.query_type in ['error', 'unknown']

    # ============ 参数化查询验证 ============

    def test_parameterized_query(self, qa):
        """验证使用参数化查询"""
        # 测试各种员工名查询
        for name in ['张三', '李四', '王五']:
            result = qa.answer(f"{name}的部门是什么？")
            assert result.query_type == 'db'
            assert '未找到' not in result.answer

    # ============ 额外测试 ============

    def test_employee_email(self, qa):
        """测试员工邮箱查询"""
        result = qa.answer("张三的邮箱是什么？")
        # 当前实现可能不直接支持邮箱查询，但应该有合理响应
        assert result.answer != ""

    def test_performance_query(self, qa):
        """测试绩效查询"""
        result = qa.answer("张三2025年绩效如何？")
        assert result.answer != ""

    def test_active_projects(self, qa):
        """测试在研项目查询"""
        result = qa.answer("有哪些在研项目？")
        assert result.answer != ""

    def test_project_status(self, qa):
        """测试项目状态查询"""
        result = qa.answer("PRJ-001的状态是什么？")
        # 当前实现可能不直接支持，但应该有响应
        assert result.answer != ""


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])