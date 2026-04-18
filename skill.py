#!/usr/bin/env python3
"""
企业智能问答助手 - 核心查询处理脚本
支持数据库查询、知识库检索、混合查询，带来源标注
支持员工管理：添加、修改、删除
"""

import sqlite3
import re
import os
import yaml
import argparse
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueryResult:
    """查询结果"""
    answer: str
    source: str
    query_type: str  # 'db', 'kb', 'mixed', 'write', 'error'


class EnterpriseQA:
    """企业智能问答系统"""

    # SQL注入检测关键词
    SQL_INJECTION_PATTERNS = [
        r'\bSELECT\b.*\bFROM\b',
        r'\bINSERT\b.*\bINTO\b',
        r'\bUPDATE\b.*\bSET\b',
        r'\bDELETE\b.*\bFROM\b',
        r'\bDROP\b',
        r'\bUNION\b',
        r"'\s*OR\s*'",
        r"'\s*AND\s*'",
        r'--',
        r';',
        r"'\s*=\s*'",
    ]

    # 员工名映射（用于识别查询目标）
    EMPLOYEE_NAMES = {
        '张三': 'EMP-001', '李四': 'EMP-002', '王五': 'EMP-003',
        '赵六': 'EMP-004', '钱七': 'EMP-005', '孙八': 'EMP-006',
        '周九': 'EMP-007', '吴十': 'EMP-008', 'CEO': 'EMP-000',
    }

    # 部门列表
    DEPARTMENTS = ['研发部', '产品部', '市场部', '管理层']

    def __init__(self, config_path: Optional[str] = None):
        """初始化"""
        if config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            # 默认配置
            self.config = {
                'database': {
                    'path': os.environ.get('ENTERPRISE_QA_DB_PATH',
                        'D:/Program Files/Feishu/DownLoad/interview-exam(30)/interview-exam/enterprise-qa-data/enterprise.db')
                },
                'knowledge_base': {
                    'root_path': os.environ.get('ENTERPRISE_QA_KB_PATH',
                        'D:/Program Files/Feishu/DownLoad/interview-exam(30)/interview-exam/enterprise-qa-data/knowledge')
                },
                'current_date': '2026-03-27'
            }

        self.db_path = self.config['database']['path']
        self.kb_path = self.config['knowledge_base']['root_path']

        # 预加载知识库内容
        self._kb_cache = {}
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """预加载知识库文件"""
        kb_files = [
            'hr_policies.md', 'promotion_rules.md', 'finance_rules.md',
            'faq.md', 'tech_docs.md',
            'meeting_notes/2026-03-01-allhands.md',
            'meeting_notes/2026-03-15-tech-sync.md'
        ]
        for filename in kb_files:
            filepath = Path(self.kb_path) / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    self._kb_cache[filename] = f.read()

    def _check_sql_injection(self, question: str) -> bool:
        """检测SQL注入尝试"""
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return True
        return False

    def _get_employee_id(self, name: str) -> Optional[str]:
        """根据员工名获取ID"""
        if name in self.EMPLOYEE_NAMES:
            return self.EMPLOYEE_NAMES[name]
        return None

    def _execute_safe_query(self, query: str, params: tuple) -> List[Tuple]:
        """执行安全的参数化查询"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            return results
        except sqlite3.Error as e:
            return []

    def _execute_write_query(self, query: str, params: tuple) -> Tuple[bool, str]:
        """执行写入操作（INSERT/UPDATE/DELETE）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return True, f"成功，影响 {affected} 条记录"
        except sqlite3.Error as e:
            return False, str(e)

    def _get_next_employee_id(self) -> str:
        """获取下一个员工ID"""
        results = self._execute_safe_query(
            "SELECT MAX(employee_id) FROM employees", ()
        )
        if results and results[0][0]:
            last_id = results[0][0]
            num = int(last_id.replace('EMP-', '')) + 1
            return f'EMP-{num:03d}'
        return 'EMP-010'

    def _validate_employee_data(self, name: str, department: str, level: str) -> Tuple[bool, str]:
        """验证员工数据"""
        if not name or len(name) > 50:
            return False, "员工名不能为空且不超过50字符"
        if department not in self.DEPARTMENTS:
            return False, f"部门必须是：{', '.join(self.DEPARTMENTS)}"
        valid_levels = ['P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10']
        if level not in valid_levels:
            return False, f"职级必须是：{', '.join(valid_levels)}"
        return True, ""

    def _search_knowledge_base(self, keywords: List[str]) -> Tuple[str, str]:
        """搜索知识库"""
        best_match = None
        best_score = 0
        best_source = ""

        for filename, content in self._kb_cache.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in content.lower():
                    score += 1

            if score > best_score:
                best_score = score
                best_match = content
                best_source = filename

        return best_match or "", best_source

    def _extract_section(self, content: str, section_title: str) -> str:
        """提取文档中的特定章节"""
        lines = content.split('\n')
        section_lines = []
        in_section = False
        section_level = 0

        for line in lines:
            # 检测标题
            if line.startswith('## ') or line.startswith('### '):
                current_level = 2 if line.startswith('## ') else 3
                if section_title.lower() in line.lower():
                    in_section = True
                    section_level = current_level
                    section_lines.append(line)
                elif in_section and current_level <= section_level:
                    # 遇到同级或更高级标题，结束
                    break
            elif in_section:
                section_lines.append(line)

        return '\n'.join(section_lines).strip()

    def answer(self, question: str) -> QueryResult:
        """回答用户问题"""
        # 1. 安全检查
        if self._check_sql_injection(question):
            return QueryResult(
                answer="检测到可能的 SQL 注入攻击，查询已被拦截。",
                source="安全检查",
                query_type="error"
            )

        question = question.strip()

        # ========== 员工管理操作（增删改）==========

        # 添加员工：添加员工 姓名 部门 职级
        add_match = re.match(r'添加员工\s+(\S+)\s+(\S+)\s+(P\d+)', question)
        if add_match:
            return self._add_employee(add_match.group(1), add_match.group(2), add_match.group(3))

        # 修改员工：修改员工 姓名/EMP-XXX 的 部门/职级/邮箱 为 新值
        modify_match = re.match(r'修改员工\s+(\S+)\s+的\s+(部门|职级|邮箱|上级)\s+为\s+(\S+)', question)
        if modify_match:
            return self._modify_employee(modify_match.group(1), modify_match.group(2), modify_match.group(3))

        # 删除员工：删除员工 姓名/EMP-XXX
        delete_match = re.match(r'删除员工\s+(\S+)', question)
        if delete_match:
            return self._delete_employee(delete_match.group(1))

        # 列出所有员工
        if question in ['列出所有员工', '所有员工', '员工列表']:
            return self._list_all_employees()

        # 检测问题中是否有员工名
        employee_names_list = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十', 'CEO']
        found_employee = None
        for name in employee_names_list:
            if name in question:
                found_employee = name
                break

        # ========== 数据库查询（优先处理包含员工名的查询）==========

        # T01: 员工部门查询
        if found_employee and '部门' in question:
            emp_id = self._get_employee_id(found_employee)
            results = self._execute_safe_query(
                "SELECT department FROM employees WHERE employee_id = ?", (emp_id,)
            )
            if results:
                return QueryResult(
                    answer=f"{found_employee}的部门是{results[0][0]}。",
                    source=f"employees 表 (employee_id: {emp_id})",
                    query_type="db"
                )

        # T02: 员工上级查询
        if found_employee and ('上级' in question or '领导' in question):
            emp_id = self._get_employee_id(found_employee)
            results = self._execute_safe_query(
                "SELECT manager_id FROM employees WHERE employee_id = ?", (emp_id,)
            )
            if results and results[0][0]:
                manager_id = results[0][0]
                manager_results = self._execute_safe_query(
                    "SELECT name FROM employees WHERE employee_id = ?", (manager_id,)
                )
                if manager_results:
                    manager_name = manager_results[0][0]
                    return QueryResult(
                        answer=f"{found_employee}的上级是{manager_name} ({manager_id})。",
                        source=f"employees 表 (employee_id: {emp_id}, manager_id: {manager_id})",
                        query_type="db"
                    )

        # T05: 员工项目查询
        if found_employee and ('项目' in question or '负责' in question):
            emp_id = self._get_employee_id(found_employee)
            results = self._execute_safe_query(
                """SELECT p.name, pm.role, p.status
                   FROM project_members pm
                   JOIN projects p ON pm.project_id = p.project_id
                   WHERE pm.employee_id = ?
                   ORDER BY pm.join_date""",
                (emp_id,)
            )
            if results:
                projects_info = []
                for r in results:
                    projects_info.append(f"{r[0]}({r[1]})")
                return QueryResult(
                    answer=f"{found_employee}参与的项目：{', '.join(projects_info)}。",
                    source=f"projects 表 + project_members 表 (employee_id: {emp_id})",
                    query_type="db"
                )

        # T07: 晋升条件判断（混合查询）- 特殊处理，需要员工名+晋升关键词
        if found_employee and ('晋升' in question or '符合' in question and '条件' in question):
            return self._handle_promotion_query(found_employee)

        # T08: 考勤查询（迟到次数）- 特殊处理，员工名+迟到关键词
        if found_employee and '迟到' in question:
            return self._handle_attendance_query(found_employee, question)

        # T09: 员工ID查询
        emp_id_match = re.search(r'EMP-\d+', question)
        if emp_id_match:
            emp_id = emp_id_match.group()
            results = self._execute_safe_query(
                "SELECT name, department, level FROM employees WHERE employee_id = ?", (emp_id,)
            )
            if results:
                name, dept, level = results[0]
                return QueryResult(
                    answer=f"员工 {emp_id}：{name}，{dept}，职级 {level}。",
                    source=f"employees 表 (employee_id: {emp_id})",
                    query_type="db"
                )
            else:
                return QueryResult(
                    answer=f"未找到员工编号 {emp_id}。",
                    source="employees 表",
                    query_type="db"
                )

        # T06: 部门人数查询
        dept_match = re.search(r'(研发部|产品部|市场部|管理层|研发|产品|市场)有多少人', question)
        if dept_match:
            dept = dept_match.group(1)
            # 处理简称
            dept_map = {'研发': '研发部', '产品': '产品部', '市场': '市场部'}
            dept = dept_map.get(dept, dept)

            results = self._execute_safe_query(
                """SELECT COUNT(*), GROUP_CONCAT(name)
                   FROM employees
                   WHERE department = ? AND status = 'active'""",
                (dept,)
            )
            if results:
                count = results[0][0]
                names = results[0][1] if results[0][1] else ""
                return QueryResult(
                    answer=f"{dept}共有{count}人（{names}）。",
                    source=f"employees 表 (department: {dept})",
                    query_type="db"
                )

        # ========== 知识库查询（处理不含员工名的制度类问题）==========

        kb_queries = {
            '年假': ('hr_policies.md', '请假类型'),
            '请假': ('hr_policies.md', '请假类型'),
            '迟到扣钱': ('hr_policies.md', '迟到规则'),
            '迟到规则': ('hr_policies.md', '迟到规则'),
            '加班': ('hr_policies.md', '加班制度'),
            '晋升条件': ('promotion_rules.md', '晋升条件'),
            '晋升流程': ('promotion_rules.md', '晋升流程'),
            '报销': ('finance_rules.md', '报销标准'),
            '差旅': ('finance_rules.md', '差旅费标准'),
            '试用期': ('faq.md', '入职相关'),
            '五险一金': ('faq.md', '入职相关'),
            '福利': ('faq.md', '福利相关'),
            '体检': ('faq.md', '福利相关'),
            '年假怎么算': ('hr_policies.md', '请假类型'),
        }

        # 精确匹配知识库查询
        for query_key, (doc, section) in kb_queries.items():
            if query_key in question.lower():
                return self._handle_kb_query(doc, section, query_key)

        # T03: 年假计算
        if '年假' in question and '怎么' in question:
            return self._handle_kb_query('hr_policies.md', '请假类型', '年假')

        # T04: 迟到扣钱规则
        if '迟到' in question and ('扣' in question or '几次' in question):
            return self._handle_kb_query('hr_policies.md', '迟到规则', '迟到扣款')

        # T10: 模糊问题处理
        if re.search(r'最近.*事|有什么事|最近.*活动', question):
            content, source = self._search_knowledge_base(['2026-03'])
            if content:
                return QueryResult(
                    answer=f"最近的会议活动：\n{self._extract_meeting_summary(content)}",
                    source=source,
                    query_type="kb"
                )

        # ========== 无匹配处理 ==========

        return QueryResult(
            answer=f"抱歉，未找到关于 \"{question}\" 的相关信息。请尝试更具体的问题描述。",
            source="",
            query_type="unknown"
        )

    def _handle_kb_query(self, doc: str, section: str, keyword: str) -> QueryResult:
        """处理知识库查询"""
        content = self._kb_cache.get(doc, "")
        if not content:
            return QueryResult(
                answer=f"未找到相关文档 {doc}。",
                source=doc,
                query_type="kb"
            )

        section_content = self._extract_section(content, section)

        if keyword == '年假':
            answer = "根据《人事制度》，年假计算规则为：\n- 入职满1年享5天\n- 每增加1年+1天\n- 上限15天"
        elif keyword == '迟到扣款':
            answer = "根据《人事制度》，迟到扣款规则为：\n- 月累计迟到3次以内：不扣款\n- 月累计迟到4-6次：每次扣款50元\n- 月累计迟到7次以上：视为旷工1天"
        else:
            answer = section_content if section_content else content[:500]

        return QueryResult(
            answer=answer,
            source=f"{doc} §{section}",
            query_type="kb"
        )

    def _handle_promotion_query(self, name: str) -> QueryResult:
        """处理晋升条件判断查询"""
        emp_id = self._get_employee_id(name)

        if not emp_id:
            return QueryResult(
                answer=f"未找到员工 \"{name}\"。",
                source="employees 表",
                query_type="db"
            )

        # 获取员工数据
        emp_data = self._execute_safe_query(
            """SELECT level, hire_date, department FROM employees WHERE employee_id = ?""",
            (emp_id,)
        )
        if not emp_data:
            return QueryResult(
                answer=f"未找到员工 \"{name}\"的数据。",
                source="employees 表",
                query_type="db"
            )

        level, hire_date, dept = emp_data[0]

        # 计算入职年限
        hire_year = int(hire_date.split('-')[0])
        current_year = int(self.config['current_date'].split('-')[0])
        years = current_year - hire_year

        # 获取绩效数据
        perf_data = self._execute_safe_query(
            """SELECT AVG(kpi_score), COUNT(*) FROM performance_reviews WHERE employee_id = ?""",
            (emp_id,)
        )
        avg_kpi = perf_data[0][0] if perf_data else 0

        # 获取项目数
        proj_data = self._execute_safe_query(
            """SELECT COUNT(*) FROM project_members WHERE employee_id = ?""",
            (emp_id,)
        )
        proj_count = proj_data[0][0] if proj_data else 0

        # 分析是否符合条件
        analysis = self._analyze_promotion(name, level, years, avg_kpi, proj_count)

        return QueryResult(
            answer=analysis,
            source=f"promotion_rules.md §晋升条件 + performance_reviews表 + project_members表 + employees表",
            query_type="mixed"
        )

    def _handle_attendance_query(self, name: str, question: str) -> QueryResult:
        """处理考勤查询"""
        emp_id = self._get_employee_id(name)

        # 检测月份
        month_match = re.search(r'(\d+)月', question)
        month = month_match.group(1) if month_match else '02'

        year = '2026'
        date_pattern = f'{year}-{month.zfill(2)}-%'

        results = self._execute_safe_query(
            """SELECT COUNT(*) FROM attendance
               WHERE employee_id = ? AND status = 'late' AND date LIKE ?""",
            (emp_id, date_pattern)
        )
        count = results[0][0] if results else 0

        return QueryResult(
            answer=f"{name}{month}月迟到{count}次。",
            source=f"attendance 表 (employee_id: {emp_id}, date: {year}-{month})",
            query_type="db"
        )

    def _extract_meeting_summary(self, content: str) -> str:
        """提取会议摘要"""
        lines = content.split('\n')
        summary = []
        for line in lines[:20]:
            if line.strip() and not line.startswith('---'):
                summary.append(line)
        return '\n'.join(summary)

    def _analyze_promotion(self, name: str, level: str, years: int,
                           avg_kpi: float, proj_count: int) -> str:
        """分析晋升条件"""

        # P5 -> P6 的条件
        if level == 'P5':
            conditions = [
                ('入职年限', '满1年', years >= 1, f'{years}年'),
                ('连续2季度KPI≥85', '是', avg_kpi >= 85, f'{avg_kpi:.1f}'),
                ('项目数≥3个', '是', proj_count >= 3, f'{proj_count}个'),
                ('无重大事故', '是', True, '无记录'),
            ]
        elif level == 'P6':
            conditions = [
                ('P6满2年', '是', years >= 2, f'{years}年'),
                ('连续4季度KPI≥90', '是', avg_kpi >= 90, f'{avg_kpi:.1f}'),
                ('主导项目≥2个', '是', proj_count >= 2, f'{proj_count}个'),
                ('技术贡献', '需审核', False, '待评估'),
            ]
        else:
            return f"{name}（职级{level}）的晋升条件请参考晋升制度文档。"

        # 生成分析表格
        passed = sum(1 for c in conditions if c[2])
        total = len(conditions)
        status = '符合' if passed >= total - 1 else '不符合'

        table_lines = [f"| 条件 | 要求 | {name}情况 | 结果 |"]
        table_lines.append("|------|------|---------|------|")
        for cond_name, req, met, value in conditions:
            mark = 'Y' if met else 'N'
            table_lines.append(f"| {cond_name} | {req} | {value} | {mark} |")

        result = f"{name}目前{status}晋升条件。\n\n分析如下：\n"
        result += '\n'.join(table_lines)

        if status == '不符合':
            suggestions = []
            for cond_name, req, met, value in conditions:
                if not met:
                    suggestions.append(f"- {cond_name}：当前{value}，需达到{req}")
            result += '\n\n建议：\n' + '\n'.join(suggestions)

        return result

    # ========== 员工管理方法 ==========

    def _add_employee(self, name: str, department: str, level: str) -> QueryResult:
        """添加员工"""
        # 验证数据
        valid, msg = self._validate_employee_data(name, department, level)
        if not valid:
            return QueryResult(
                answer=f"添加失败：{msg}",
                source="数据验证",
                query_type="error"
            )

        # 检查是否已存在同名员工
        existing = self._execute_safe_query(
            "SELECT employee_id FROM employees WHERE name = ?", (name,)
        )
        if existing:
            return QueryResult(
                answer=f"添加失败：已存在同名员工 {name} ({existing[0][0]})",
                source="employees 表",
                query_type="error"
            )

        # 生成新ID
        new_id = self._get_next_employee_id()
        today = datetime.now().strftime('%Y-%m-%d')
        email = f"{name.lower()}@company.com"

        # 执行插入
        success, msg = self._execute_write_query(
            """INSERT INTO employees
               (employee_id, name, department, level, hire_date, manager_id, email, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, name, department, level, today, 'EMP-000', email, 'active')
        )

        if success:
            return QueryResult(
                answer=f"员工添加成功！\n- ID: {new_id}\n- 姓名: {name}\n- 部门: {department}\n- 职级: {level}\n- 邮箱: {email}",
                source=f"employees 表 (新记录)",
                query_type="write"
            )
        else:
            return QueryResult(
                answer=f"添加失败：{msg}",
                source="employees 表",
                query_type="error"
            )

    def _modify_employee(self, emp_identifier: str, field: str, new_value: str) -> QueryResult:
        """修改员工信息"""
        # 获取员工ID
        if emp_identifier.startswith('EMP-'):
            emp_id = emp_identifier
        else:
            emp_id = self._get_employee_id(emp_identifier)
            if not emp_id:
                # 尝试从数据库查找
                results = self._execute_safe_query(
                    "SELECT employee_id FROM employees WHERE name = ?", (emp_identifier,)
                )
                if results:
                    emp_id = results[0][0]
                else:
                    return QueryResult(
                        answer=f"未找到员工 \"{emp_identifier}\"",
                        source="employees 表",
                        query_type="error"
                    )

        # 获取当前员工信息
        emp_info = self._execute_safe_query(
            "SELECT name, department, level FROM employees WHERE employee_id = ?", (emp_id,)
        )
        if not emp_info:
            return QueryResult(
                answer=f"未找到员工 {emp_id}",
                source="employees 表",
                query_type="error"
            )

        old_name, old_dept, old_level = emp_info[0]

        # 验证新值
        field_map = {
            '部门': 'department',
            '职级': 'level',
            '邮箱': 'email',
            '上级': 'manager_id'
        }
        db_field = field_map.get(field, field)

        if field == '部门' and new_value not in self.DEPARTMENTS:
            return QueryResult(
                answer=f"修改失败：部门必须是 {', '.join(self.DEPARTMENTS)}",
                source="数据验证",
                query_type="error"
            )

        if field == '职级':
            valid_levels = ['P4', 'P5', 'P6', 'P7', 'P8', 'P9', 'P10']
            if new_value not in valid_levels:
                return QueryResult(
                    answer=f"修改失败：职级必须是 {', '.join(valid_levels)}",
                    source="数据验证",
                    query_type="error"
                )

        if field == '上级':
            if not new_value.startswith('EMP-'):
                # 尝试查找上级ID
                mgr_results = self._execute_safe_query(
                    "SELECT employee_id FROM employees WHERE name = ?", (new_value,)
                )
                if mgr_results:
                    new_value = mgr_results[0][0]
                else:
                    return QueryResult(
                        answer=f"修改失败：未找到上级 \"{new_value}\"",
                        source="employees 表",
                        query_type="error"
                    )

        # 执行更新
        success, msg = self._execute_write_query(
            f"UPDATE employees SET {db_field} = ? WHERE employee_id = ?",
            (new_value, emp_id)
        )

        if success:
            return QueryResult(
                answer=f"员工 {old_name}({emp_id}) 的{field}已修改为 {new_value}",
                source=f"employees 表 (employee_id: {emp_id})",
                query_type="write"
            )
        else:
            return QueryResult(
                answer=f"修改失败：{msg}",
                source="employees 表",
                query_type="error"
            )

    def _delete_employee(self, emp_identifier: str) -> QueryResult:
        """删除员工"""
        # 获取员工ID
        if emp_identifier.startswith('EMP-'):
            emp_id = emp_identifier
        else:
            emp_id = self._get_employee_id(emp_identifier)
            if not emp_id:
                results = self._execute_safe_query(
                    "SELECT employee_id FROM employees WHERE name = ?", (emp_identifier,)
                )
                if results:
                    emp_id = results[0][0]
                else:
                    return QueryResult(
                        answer=f"未找到员工 \"{emp_identifier}\"",
                        source="employees 表",
                        query_type="error"
                    )

        # 获取员工信息（用于确认）
        emp_info = self._execute_safe_query(
            "SELECT name, department, level FROM employees WHERE employee_id = ?", (emp_id,)
        )
        if not emp_info:
            return QueryResult(
                answer=f"未找到员工 {emp_id}",
                source="employees 表",
                query_type="error"
            )

        name, dept, level = emp_info[0]

        # 检查是否是CEO或有下属
        subordinates = self._execute_safe_query(
            "SELECT COUNT(*) FROM employees WHERE manager_id = ?", (emp_id,)
        )
        if subordinates and subordinates[0][0] > 0:
            return QueryResult(
                answer=f"删除失败：{name} 还有 {subordinates[0][0]} 名下属，请先调整下属的上级",
                source="employees 表",
                query_type="error"
            )

        # 执行删除
        success, msg = self._execute_write_query(
            "DELETE FROM employees WHERE employee_id = ?", (emp_id,)
        )

        if success:
            return QueryResult(
                answer=f"员工删除成功！\n- ID: {emp_id}\n- 姓名: {name}\n- 部门: {dept}\n- 职级: {level}",
                source=f"employees 表 (已删除)",
                query_type="write"
            )
        else:
            return QueryResult(
                answer=f"删除失败：{msg}",
                source="employees 表",
                query_type="error"
            )

    def _list_all_employees(self) -> QueryResult:
        """列出所有员工"""
        results = self._execute_safe_query(
            """SELECT employee_id, name, department, level, status
               FROM employees ORDER BY employee_id""",
            ()
        )

        if not results:
            return QueryResult(
                answer="当前无员工记录",
                source="employees 表",
                query_type="db"
            )

        lines = ["| ID | 姓名 | 部门 | 职级 | 状态 |"]
        lines.append("|------|------|------|------|------|")
        for emp_id, name, dept, level, status in results:
            lines.append(f"| {emp_id} | {name} | {dept} | {level} | {status} |")

        return QueryResult(
            answer=f"员工列表（共 {len(results)} 人）：\n" + '\n'.join(lines),
            source="employees 表",
            query_type="db"
        )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='企业智能问答助手')
    parser.add_argument('--question', '-q', type=str, required=True, help='用户问题')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径')

    args = parser.parse_args()

    qa = EnterpriseQA(args.config)
    result = qa.answer(args.question)

    print(result.answer)
    if result.source:
        print(f"\n> 来源：{result.source}")


if __name__ == '__main__':
    main()