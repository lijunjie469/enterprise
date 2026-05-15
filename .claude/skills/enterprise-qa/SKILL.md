---
name: enterprise-qa
description: 企业智能问答助手 — 查询员工信息、项目记录、考勤数据、绩效考核、公司制度、会议纪要等
---

# 企业智能问答助手 Skill

## 触发方式

用户输入以下格式之一：
- `/enterprise-qa <问题>`
- `/qa <问题>`
- `@enterprise-qa <问题>`

## 工作原理

当用户调用此 Skill 时，将用户的问题作为参数运行后台 CLI：

```bash
python cli.py "<用户问题>"
```

CLI 会自动完成：
1. **意图识别** — 判断问题是查数据库、查知识库、还是混合查询
2. **SQL 生成** — 参数化查询（防注入），查 employees/projects/attendance/performance_reviews 等表
3. **知识库检索** — BM25 + jieba 分词搜索 knowledge/ 目录下的所有 Markdown 文档
4. **结果融合** — 整合多源信息，生成自然语言回答
5. **来源标注** — 标注数据来源（数据库表名 / 知识库文件名及章节）

## 数据源

- **数据库** (`enterprise.db`): employees, projects, project_members, attendance, performance_reviews
- **知识库** (`knowledge/`): hr_policies.md, promotion_rules.md, tech_docs.md, finance_rules.md, faq.md, 会议纪要

## 支持的问题类型

| 类型 | 示例 |
|------|------|
| 纯数据库查询 | "张三的部门是什么？"、"李四的邮箱"、"研发部有多少人？" |
| 纯知识库查询 | "年假怎么计算？"、"迟到几次扣钱？"、"报销标准是什么？" |
| 混合查询 | "王五符合P5晋升P6条件吗？"、"张三2025年绩效如何？" |
| 跨表关联 | "张三负责哪些项目？"、"有哪些在研项目？" |
| 时间范围 | "张三2月迟到几次？" |

## 执行指令

1. 从用户输入中提取问题文本（去掉触发词前缀如 `/enterprise-qa` 或 `@enterprise-qa`）
2. 在 `enterprise-qa-system/` 目录下执行：
   ```
   python -X utf8 cli.py "<问题>"
   ```
3. 输出 CLI 返回的结果，注意过滤掉 jieba 的加载日志（`Building prefix dict...`、`Loading model...` 等行）
4. 如果 CLI 返回"未找到"相关问题，友好地告知用户

## 安全特性

- 所有 SQL 查询均使用参数化方式，杜绝 SQL 注入
- 对输入内容进行注入模式检测
- 仅允许 SELECT 只读查询
- 敏感字段（如 manager_id）仅通过关联查询获取名称
