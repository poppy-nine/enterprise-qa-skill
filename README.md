# 企业智能问答助手 Skill 使用说明

## 安装

1. 确保 Python 3.8+ 和 SQLite 已安装
2. 安装依赖：
```bash
pip install pyyaml pytest
```

3. 初始化数据库：
```bash
cd enterprise-qa-data
sqlite3 enterprise.db < schema.sql
sqlite3 enterprise.db < seed_data.sql
```

## 配置

修改 `config.yaml` 或设置环境变量：
```bash
export ENTERPRISE_QA_DB_PATH="./enterprise.db"
export ENTERPRISE_QA_KB_PATH="./knowledge"
```

## 使用方式

### Claude Code Skill
```
/enterprise-qa "张三的部门是什么？"
/enterprise-qa "年假怎么计算？"
/enterprise-qa "王五符合晋升条件吗？"
```

### 直接运行 Python 脚本
```bash
python skill.py -q "张三的部门是什么？"
python skill.py -q "年假怎么计算？"
python skill.py -q "王五符合晋升条件吗？"
```

## 支持的查询类型

| 类型 | 示例 | 数据源 |
|------|------|--------|
| 员工信息查询 | "张三的部门是什么？" | DB |
| 员工上级查询 | "李四的上级是谁？" | DB |
| 项目查询 | "张三负责哪些项目？" | DB |
| 部门人数 | "研发部有多少人？" | DB |
| 考勤查询 | "张三2月迟到几次？" | DB |
| 制度查询 | "年假怎么计算？" | KB |
| 迟到规则 | "迟到几次扣钱？" | KB |
| 晋升判断 | "王五符合晋升条件吗？" | DB+KB |
| 模糊问题 | "最近有什么事？" | KB |

## 测试

运行单元测试：
```bash
python -m pytest tests/test_skill.py -v
```

## 文件结构

```
enterprise-qa/
├── skill.md          # Skill 定义文件
├── skill.py          # 核心实现
├── config.yaml       # 配置文件
├── requirements.txt  # Python 依赖
└── tests/
    └── test_skill.py # 单元测试
```

## 安全特性

- SQL 注入防护：使用参数化查询
- 输入验证：检测并拦截恶意输入
- 数据源可配置：不硬编码路径