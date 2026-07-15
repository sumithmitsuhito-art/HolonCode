# Sidebar 学习进度 & 关卡选择 & c-learn 进度追踪 设计文档

> 日期：2026-07-15
> 状态：已确认

---

## 概述

三个功能改进：
1. "清空学习进度"按钮 → "查看学习进度"，点击打开进度可视化窗口（双选项卡：闯关进度 + 知识点进度），清空按钮集成到窗口内
2. "C语言知识闯关"按钮 → 点击弹出关卡选择对话框，自由选择关卡
3. c-learn（知识点学习）skill 实现 AI 自动记录和读取用户知识点掌握进度

---

## 文件变更清单

| 文件 | 操作 | 模块 |
|------|------|------|
| `src/atri/ui/progress_dialog.py` | 新建 | 进度查看对话框 |
| `src/atri/ui/level_select_dialog.py` | 新建 | 闯关关卡选择对话框 |
| `skills/c-learn/plugin.py` | 新建 | c-learn 进度追踪 |
| `skills/c-learn/SKILL.md` | 修改 | 增加进度记录指令 |
| `src/atri/ui/sidebar.py` | 修改 | 信号变更 + 知识点对话框优化 |
| `src/atri/ui/app_shell.py` | 修改 | 信号连线 + 逻辑迁移 |

---

## 模块一：进度查看对话框 `progress_dialog.py`

**窗口**：800x550，模态，深色背景（BG_MAIN）

**布局**：
- 顶部：两个 Tab 切换按钮（闯关进度 / 知识点进度），QPushButton 互斥切换
- 中部：QScrollArea + QGridLayout 卡片网格
- 底部：清空当前选项卡进度按钮（带确认对话框）

**c-tutor 选项卡卡片**：关卡编号、名称、题型图标（编程/改错/选择填空）、分数、完成状态（✅ 绿色边框 / 🔄 灰色边框）

**c-learn 选项卡卡片**：知识点编号、名称、掌握等级彩色标签（了解=灰 #9CA3AF / 理解=蓝 #3B82F6 / 掌握=绿 #10B981 / 熟练=金 #F59E0B）

---

## 模块二：闯关关卡选择对话框 `level_select_dialog.py`

**窗口**：800x550，复用知识点对话框的样式

**布局**：3 个题型分组（QGridLayout）：
- 编程题 10 关
- 改错题 5 关
- 选择/填空题 4 关

每张卡片显示关卡名称 + 完成状态/分数（读取 c-tutor-progress.json）

点击任一关卡 → 发送 `"开始闯关第X关 — {name}"`，激活 c-tutor skill

---

## 模块三：c-learn 进度追踪

### 数据文件 `data/c-learn-progress.json`

```json
{
  "total_topics": 27,
  "completed_topics": 0,
  "topics": {
    "0": {"name": "声明语法", "level": 1, "updated_at": "2026-07-15"},
    ...
  }
}
```

掌握等级：1=了解 / 2=理解 / 3=掌握 / 4=熟练

### plugin.py — 三个 Tool

| Tool 名 | 参数 | 功能 |
|---------|------|------|
| `c_learn_load_progress` | 无 | 返回所有知识点的掌握情况 |
| `c_learn_save_progress` | `topic_id: str, level: int, note: str(可选)` | 更新某个知识点的掌握等级 |
| `c_learn_reset_progress` | `confirm: str` | 确认后清空所有进度 |

激活时注入进度到 system prompt，AI 根据对话自主判断掌握程度并调用 save_progress。

---

## 模块四：Sidebar 信号 & AppShell 连线

### Sidebar 变更

| 当前 | 改为 |
|------|------|
| `clear_progress = Signal()` | `view_progress = Signal()` |
| "清空学习进度"按钮 | "查看学习进度"按钮 |
| "C语言知识闯关" → emit skill_activated | → 打开 LevelSelectDialog，选关后 emit level_selected |
| 新增：`level_selected = Signal(str, str)` | (level_id, level_name) |

### AppShell 变更

| 当前 | 改为 |
|------|------|
| `sidebar.clear_progress.connect(...)` | `sidebar.view_progress.connect(...)` |
| `_on_clear_progress` | 迁移到 ProgressDialog 内部 |
| 新增 `_on_level_selected` | 激活 c-tutor + 发送关卡选择消息 |

---

## 模块五：知识点选择对话框优化

当前 27 个纯文字按钮 → 改为卡片式布局（QFrame + QVBoxLayout），每张卡片显示：
- 知识点编号 + 名称
- 掌握等级彩色标签（读取 c-learn-progress.json，未学过的无标签）
- 通用按钮改为独立一行的大卡片样式
