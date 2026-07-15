# C 语言教学与答疑技能设计

> 2026-07-13 | 方案 A — c-tutor 含 plugin.py，c-qa 纯 SKILL.md

## 概述

为 HolonCode 创建两个 C 语言相关技能：

| 技能 | 目录 | plugin.py | 用途 |
|---|---|---|---|
| c-tutor | `skills/c-tutor/` | 是 | 闯关式 C 语言教学，讲解知识点 + 编程实战 |
| c-qa | `skills/c-qa/` | 否 | C 语言答疑，代码审查、概念解释、调试协助 |

---

## c-tutor — C 语言教学技能

### 文件结构

```
skills/c-tutor/
├── SKILL.md       # frontmatter + 关卡列表（知识点、例题、评分标准）
└── plugin.py      # 3 个工具：load_progress / save_progress / reset_progress
```

### 数据存储

进度文件 `data/c-tutor-progress.json`：

```json
{
  "total_score": 0,
  "total_levels": 10,
  "completed_levels": 0,
  "levels": {
    "01": {
      "summary": "变量与数据类型",
      "completed": false,
      "score": 0,
      "completed_at": null
    }
  }
}
```

- 存储在 `data/` 目录，由 plugin.py 读写
- `save_progress` 自动重算 `total_score` 和 `completed_levels`
- `reset_progress` 清空全部进度，需要用户二次确认

### plugin.py 工具

| 工具名 | 参数 | 返回值 | 说明 |
|---|---|---|---|
| `load_progress` | 无 | 完整进度 JSON | 读取 data/c-tutor-progress.json |
| `save_progress` | `level_id: str, summary: str, score: int` | 更新后的进度摘要 | 保存单关完成状态，自动重算总分 |
| `reset_progress` | `confirm: str` | 操作结果 | confirm="yes" 时清空全部进度 |

### SKILL.md 结构

```markdown
---
name: c-tutor
description: C语言闯关教学——讲解知识点+编程实战，逐关通关学习C语言
---

## 角色切换
进入"C语言导师"模式...

## 行为准则
- 教学流程：讲解 → 出题 → 审阅代码 → 评分 → 记录进度
- ...

## 闯关规则
- 每一关代表一个 C 语言知识点
- ...

## 评分标准
- 正确性（60分）：代码能否正确运行
- 规范性（20分）：命名、缩进、注释
- 效率（20分）：算法思路、内存管理

## 关卡列表
### 关卡 01 — 变量与数据类型
### 关卡 02 — 分支结构
...

## 结束条件
```

### 闯关流程

```
用户激活技能 → load_progress() 展示当前进度
  → 用户选择关卡（或从第一关未完成的继续）
    → AI 讲解该关知识点
    → AI 出一道编程题
    → 用户写代码（粘贴 或 写入 workspace/*.c）
    → AI 用 read_file 读取代码，审查并评分（1-100）
    → save_progress(level_id, summary, score)
    → 展示总分和进度，问"继续下一关吗？"
```

### 评分维度

| 维度 | 分值 | 说明 |
|---|---|---|
| 正确性 | 60 | 代码逻辑是否正确，能否编译通过并运行出预期结果 |
| 规范性 | 20 | 变量命名、缩进风格、是否有必要注释 |
| 效率 | 20 | 算法是否合理，有无内存泄漏风险，边界条件处理 |

---

## c-qa — C 语言答疑技能

### 文件结构

```
skills/c-qa/
└── SKILL.md       # 纯提示词，无 plugin.py
```

### SKILL.md 结构

```markdown
---
name: c-qa
description: C语言答疑模式——解答C语言概念疑问、审查代码、调试排错
---

## 角色切换
进入"C语言答疑"模式...

## 行为准则
| 场景 | 处理方式 |
|------|---------|
| 概念疑问 | 用通俗比喻解释，配合短代码示例 |
| 代码调试 | 先让用户把代码放到 workspace，read_file 后逐行审查 |
| 编译错误 | 解释错误信息含义，给出修改建议 |
| 运行结果异常 | 帮用户推理逻辑，用 printf 大法定位问题 |
| 最佳实践 | 指出问题，解释为什么不好，给出改进写法 |

## 知识范围
- C89/C99/C11/C17 标准差异
- 指针、内存管理、结构体、联合体、文件 I/O
- 常见未定义行为（UB）
- 预处理、编译链接流程
- 不熟悉的领域直接承认，不要瞎编

## 结束条件
- 用户说"可以了"、"换话题"、"没别的问题了"等，调用 deactivate_skill("c-qa") 退出
```

---

## 与现有系统的兼容性

- 两个技能都遵循现有的 SKILL.md frontmatter + Markdown 格式
- c-tutor 的 plugin.py 遵循 `@tool` 装饰器规范（skill_loader.py:27-54）
- 进度文件存放在 `data/` 目录，与 `MemoryForUser.json`、`sessions.json` 同级
- 技能上限 MAX_ACTIVE_SKILLS=3，LRU 淘汰策略不变
- 两个技能可通过 `/c-tutor`、`/c-qa` 斜杠命令激活

## 技术实现要点

### c-tutor/plugin.py

- 3 个 `@tool` 装饰的普通函数（同步，不需要 async）
- 进度 JSON 的读写需要文件锁或原子写入（先写临时文件再 rename）
- `save_progress` 的 `level_id` 与 SKILL.md 中的关卡编号对应
- `reset_progress` 必须检查 `confirm == "yes"` 才执行

### c-qa/SKILL.md

- 纯静态提示词，无运行时依赖
- 利用已有的 `read_file` 工具读取用户代码
- 不需要任何新代码
