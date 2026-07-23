# 结构化分析安全机制

## 分析门禁

后端开始调用文本模型前必须同时满足：

1. 题目存在独立的用户确认记录；
2. 当前确认文字的 SHA-256 与确认时保存的哈希一致；
3. 已配置并启用文本模型；
4. Provider 密钥可以由当前 Windows 用户解密。

任一条件不满足时，不会调用模型。

## 输入隔离

文本模型只接收：

- 用户确认后的题目快照；
- 用户确认的学科和年级；
- 用户可选填写的答案和解题过程。

原始图片、初始识别文字和未确认的原始输入不会混入分析提示词。题目文字放在数据边界中，并明确视为不可信内容，防止题目中的提示词改变系统任务。

## 信息不足

模型必须先判断 `question_completeness`。当结果为 `partial` 或 `uncertain` 时：

- `missing_information` 必须非空；
- `final_answer`、`solution_overview`、`memory_tip` 必须为空；
- `solution_steps` 和 `next_time_checklist` 必须为空；
- 页面显示“信息不足，无法可靠分析”；
- 用户需要返回确认页补充题目。

违反规则的模型输出无法通过 Pydantic Schema，不会保存为可用分析。

## 结构化输出

- OpenAI 兼容接口优先使用原生 JSON Schema；
- 不支持 JSON Schema 的兼容服务可降级为 JSON Object，并在提示词中附带 Schema；
- Gemini 使用 JSON 响应类型及响应 Schema；
- 所有结果仍需经过后端 Pydantic 校验；
- 保存模型名称、分析耗时、`analysis-v1` 和 `analysis-schema-v1`。

## 确定性复核

当前仅对能够安全识别的简单四则运算进行代码复核。结果分为：

- `verified`：代码结果与 AI 一致；
- `conflict`：代码结果与 AI 不一致；
- `not_applicable`：当前题型不适用；
- `verification_failed`：无法可靠计算。

发生冲突时不会静默修改 AI 答案，而是在页面明确警告用户重新分析或人工核对。
