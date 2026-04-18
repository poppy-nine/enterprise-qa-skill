---
name: enterprise-qa
description: 企业智能问答助手 - 查询员工信息、项目、考勤、绩效数据及公司制度文档
---

# 企业智能问答助手

根据用户问题，自动判断查询类型，选择合适的数据源（数据库/知识库），生成准确且有依据的回答。

## 使用方式

```
/enterprise-qa "张三的部门是什么？"
/enterprise-qa "年假怎么计算？"
/enterprise-qa "王五符合晋升条件吗？"
```

## 核心逻辑

### 1. 意图识别

分析问题关键词判断查询类型：
- **数据库查询**：员工名、部门、项目、考勤、绩效、邮箱、上级等
- **知识库查询**：年假、迟到、请假、晋升、报销、制度、福利等
- **混合查询**：晋升条件判断（需要员工数据+晋升规则对比）

### 2. 数据源

- 数据库：SQLite (`enterprise.db`)
  - employees（员工信息）
  - projects（项目记录）
  - project_members（项目成员）
  - attendance（考勤记录）
  - performance_reviews（绩效考核）

- 知识库：`knowledge/` 目录
  - hr_policies.md（人事制度）
  - promotion_rules.md（晋升标准）
  - finance_rules.md（财务制度）
  - faq.md（常见问题）
  - meeting_notes/（会议纪要）

### 3. 查询执行

执行以下 Python 脚本处理查询：

```python
# 运行查询脚本
python skill.py --question "用户问题"
```

### 4. 输出格式

回答需包含：
- 自然语言回答
- 来源标注（表名/字段 或 文档名/章节）

示例：
```
张三的邮箱是 zhangsan@company.com。

> 来源：employees 表 (employee_id: EMP-001)
```

## 安全要求

- 使用参数化查询防止 SQL 注入
- 检测并拒绝恶意输入
- 数据源路径通过配置文件指定，不硬编码