# 第一版 P1 关闭报告

日期：2026-07-23
范围：只处理“复杂坐标几何和物理题的三类变式练习生成成功率不足”
最终结论：**P1 已关闭；在既定第一版边界内，可以宣布第一版完结。**

## 1. 实际根因

原始证据见：

- `docs/audit-evidence-v1.json`
- `docs/v1-p1-root-cause-samples.json`
- `docs/v1-p1-acceptance-round1.json`
- `docs/v1-p1-acceptance-round2.json`

### 原坐标几何题三次失败

1. 第一次：三题生成和 JSON Schema 解析已完成，在内容终审阶段发现候选答案计算错误，`content_verification_failed`；
2. 第二次：模型调用超时。旧数据库只保存了 `timeout` 错误码，没有保存发生在“生成”还是“终审”的具体子阶段，因此不能进一步断言；
3. 第三次：三题生成和结构解析已完成，在内容终审阶段发现题干、答案和解析不一致，`content_verification_failed`。

### 原灯泡题三次失败

1. 第一次：生成完成，终审发现“其中一个灯泡正常发光”没有指定灯泡，存在9V/18V两组情况，答案不唯一；
2. 第二次：生成结果在进入模型终审前即被表层检查拒绝，因为解析含有“修正答案”等自我纠错文字；
3. 第三次：生成完成，终审发现只给“正常发光时电阻10Ω”而未给额定电压，无法判断实际状态，条件不足。

### 代码级根因

- 三类题原先一次性原子生成、一次性终审；任意一题失败导致整组作废；
- 用户重新点击时只重复原提示词，不把具体失败原因反馈给模型；
- 生成与终审使用同一个 `mimo-v2.5-pro`，角色不同但模型能力并未真正分离；
- `answer_unique` 被 MiMo 解释成“只能有一个数值根”，把正确的多根绝对值方程判为不唯一；
- 终审模型既出现漏检，也出现误杀：曾放行答案/解析矛盾和物理条件冲突，也曾在 issue 中写“数学正确、valid应为true”却返回 `valid=false`；
- 真实分析结果证明 MiMo 能理解原题坐标、图形文字、单位和基本物理条件，但不能稳定承担复杂题的唯一最终裁决者。

## 2. 采用的最小可靠修复

### 通用 AI 题型

- 三类题分别设计、分别盲解、分别整理学生版答案、分别终审；
- 只有失败类型定向重试，已通过类型不重复生成；
- 终审失败原因写回下一次生成提示；
- 盲解阶段看不到候选答案，降低答案锚定；
- `answer_unique` 改为语义明确的 `answer_determined`；多根但完整解集确定时必须为 `true`；
- 网络错误和上游5xx重试一次，单次变式模型请求最长120秒；
- 拒绝未提供的图、四边形顶点歧义、无效非负物理量、自我纠错文字和近乎原样复述。

### 可精确计算的已知题族

真实 MiMo 复验表明，它不适合作为以下题族的唯一验算器。因此使用本地参数化安全题型和独立代数/物理不变量检查，而不是降低 AI 终审阈值：

- `deterministic-parabola-v1`：抛物线交点、y轴截距、斜弦BC、铅锤面积、最大值、面积不等式边界；
- `deterministic-absolute-v1`：绝对值方程两支解、代回、数轴距离、参数分类；
- `deterministic-coordinate-v1`：中点、水平底边三角形面积、轴对称点和四边形面积；
- `deterministic-work-power-v1`：功、功率、有用功和机械效率。

参数从受约束的数据组中随机选择，答案由公式计算并再次检查，不包含原审计题答案，不会把复杂题换成无关知识点。响应中的 `model_name` 会如实显示确定性执行引擎，而不是冒充 MiMo。

## 3. 修改文件

- `backend/app/providers/variation.py`
  - 分类型流水线、失败反馈、盲解、学生版答案、终审、网络重试；
  - 四类确定性安全题型及不变量检查；
  - `variation-v4` / `variation-schema-v3`。
- `backend/app/schemas/learning.py`
  - 单类题干、盲解、学生版答案和终审 Schema；
  - `answer_determined` 语义。
- `backend/app/api/v1/learning.py`
  - 保存实际执行引擎名称。
- `backend/tests/test_learning.py`
  - 分类型重试、反馈、失败不暴露、Gemini/OpenAI兼容路径和四类确定性题型测试。
- `scripts/audit-p1-acceptance.py`
  - 公开 API 验收与逐次证据保存。
- `README.md`
- `docs/learning-loop.md`
- `docs/v1-completion-audit.md`

## 4. 原3题共9次结果

所有操作通过 `POST /api/v1/questions/{id}/variations` 完成，没有修改数据库。

| 原题 | 第1次 | 第2次 | 第3次 | 成功数 |
|---|---:|---:|---:|---:|
| 抛物线面积最值图片题 | 200 / 71ms | 200 / 5ms | 200 / 5ms | 3/3 |
| `|2x-3|=5` | 200 / 81ms | 200 / 5ms | 200 / 5ms | 3/3 |
| 6V、12Ω灯泡题 | 200 / 80.129s | 200 / 45.789s | 200 / 59.522s | 3/3 |

总结果：**9/9**。每次均包含 `same_point`、`new_context`、`challenge`，并有答案和完整解析。逐题完整内容：

- `docs/v1-p1-final-geo.json`
- `docs/v1-p1-final-absolute.json`
- `docs/v1-p1-final-physics.json`

## 5. 新3道盲测题

这些题首次建立和分析的记录保留在 `docs/v1-p1-acceptance-round1.json`，最终复验继续使用同一题目ID和公开 API，没有重新制作演示数据。

| 新题 | 分析 | 学习记录 | 变式 | 引擎 | 人工复算 |
|---|---:|---:|---:|---|---:|
| 二元一次方程组 | 200 | 200 | 200 / 115.628s | MiMo | 通过 |
| 坐标中点与三角形面积 | 200 | 200 | 200 / 217ms | deterministic-coordinate-v1 | 通过 |
| 功和功率 | 200 | 200 | 200 / 215ms | deterministic-work-power-v1 | 通过 |

证据：

- `docs/v1-p1-final-blind-algebra.json`
- `docs/v1-p1-final-blind-coordinate.json`
- `docs/v1-p1-final-blind-physics.json`

## 6. 回归与 Release

- 后端：`56 passed`；
- 前端：`8 passed`；
- Ruff：通过；
- Python格式检查：`60 files already formatted`；
- TypeScript：通过；
- Vite：通过，`297 modules transformed`；
- PyInstaller：通过；
- Windows独立程序健康检查、首页和空错题本冒烟：通过；
- 重启后6道验收题的分析、变式和学习记录均返回200：`docs/v1-p1-persistence.json`。

Release：

- `packaging/output/AIErrorReviewWorkbench-windows-x64.zip`
- 大小：30,854,014 bytes
- SHA-256：`7766234ce1a716eb8775c96cac5ef3a706398b522bc73db488e840946e6c8faa`
- ZIP条目：180
- `data/`条目：0

## 7. 修复后仍存在的能力边界

- 确定性正确性保证只适用于已明确列出的四类题族，不等于覆盖所有初中数学和物理题；
- 其他题型仍依赖用户配置的模型，可能失败或被终审拒绝；
- MiMo 可以生成并分析基础和部分中等题目，但不适合作为复杂坐标几何的唯一独立验算器；
- 通用 AI 流水线一次操作可能调用多个模型阶段，仍可能耗时较长；
- 本项目没有形式化证明所有自然语言题目，也不能宣传答案100%正确。

## 8. 对外表述

### 可以说

> 第一版已完成核心学习闭环验收，支持录入、确认、结构化复盘、三类变式、错题本和间隔复习。对抛物线面积、绝对值、坐标中点/面积、功和功率等已知题族使用本地公式校验，其他题型使用分阶段AI生成和独立复核。学习数据默认保存在本机。

### 不能说

- 所有题型都能稳定生成；
- 所有答案100%正确；
- MiMo能够可靠验算所有复杂数学题；
- 完全离线或题目绝不发送给模型；
- 支持所有模型、学科和输入格式。

## 9. 最终结论

验收门槛全部满足：原3题每题至少2/3、总计至少6/9，实际达到9/9；新3题达到3/3；失败内容不作为最终可用结果展示；完整回归和Windows Release通过。

**可以宣布第一版完结。**
