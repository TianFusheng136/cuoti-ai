import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App, { queryClient } from "./App";

function variationResult() {
  return {
    id: "variation-1", provider_config_id: "provider-1", model_name: "text-model",
    prompt_version: "variation-v1", schema_version: "variation-schema-v1", duration_ms: 18,
    created_at: "2026-07-21T00:00:00Z",
    variants: [
      { type: "same_point", title: "同知识点巩固", question: "计算 $4+5$。", answer: "$9$", solution: "$4+5=9$。", knowledge_points: ["整数加法"], difficulty: "basic" },
      { type: "new_context", title: "换场景迁移", question: "3 支笔加 6 支笔是多少？", answer: "9 支", solution: "$3+6=9$。", knowledge_points: ["整数加法"], difficulty: "basic" },
      { type: "challenge", title: "提高难度", question: "计算 $12+19$。", answer: "$31$", solution: "$12+19=31$。", knowledge_points: ["进位加法"], difficulty: "medium" },
    ],
  };
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.restoreAllMocks();
});

describe("应用骨架", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    const providers: Array<Record<string, unknown>> = [];
    const questions = new Map<string, Record<string, unknown>>();
    let analyzed = false;
    let variantsGenerated = false;
    let confirmation: Record<string, unknown> | null = null;
    let learning = {
      question_id: "question-1",
      actual_error_reason: null as string | null,
      actual_error_note: null as string | null,
      mastery_status: "new",
      starred: false,
      review_count: 0,
      next_review_at: "2026-07-21T00:00:00Z",
      last_reviewed_at: null,
      updated_at: "2026-07-21T00:00:00Z",
    };
    vi.spyOn(window, "confirm").mockReturnValue(true);
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = input.toString();
        if (url === "/api/v1/health") {
          return { ok: true, json: async () => ({ status: "ok" }) } as Response;
        }
        if (url === "/api/v1/providers" && (!init?.method || init.method === "GET")) {
          return { ok: true, json: async () => providers } as Response;
        }
        if (url === "/api/v1/providers" && init?.method === "POST") {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          const provider = {
            ...body,
            id: "provider-1",
            api_key: undefined,
            has_api_key: true,
            api_key_masked: "••••••••",
            last_test_status: null,
            last_tested_at: null,
            created_at: "2026-07-21T00:00:00Z",
            updated_at: "2026-07-21T00:00:00Z",
          };
          providers.push(provider);
          return { ok: true, json: async () => provider } as Response;
        }
        if (url === "/api/v1/providers/provider-1/test" && init?.method === "POST") {
          return {
            ok: true,
            json: async () => ({ success: true, message: "连接成功，已找到配置的模型。", latency_ms: 12 }),
          } as Response;
        }
        if (url === "/api/v1/questions" && init?.method === "POST") {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          const question = {
            id: "question-1",
            input_type: body.input_type,
            source_text: body.source_text ?? null,
            status: "draft",
            assets: [],
          };
          questions.set("question-1", question);
          return { ok: true, json: async () => question } as Response;
        }
        if (url === "/api/v1/questions/question-1/image" && init?.method === "POST") {
          const question = questions.get("question-1");
          if (question) question.assets = [{ id: "asset-1", mime_type: "image/png", width: 800, height: 600 }];
          return { ok: true, json: async () => ({ id: "asset-1" }) } as Response;
        }
        if (url === "/api/v1/questions/question-1" && (!init?.method || init.method === "GET")) {
          return { ok: true, json: async () => questions.get("question-1") } as Response;
        }
        if (url === "/api/v1/questions/question-1/confirmation" && (!init?.method || init.method === "GET")) {
          if (!confirmation) return { ok: false, status: 404, json: async () => ({ detail: "尚未确认" }) } as Response;
          return { ok: true, json: async () => confirmation } as Response;
        }
        if (url === "/api/v1/questions/question-1/recognition" && (!init?.method || init.method === "GET")) {
          return { ok: false, status: 404, json: async () => ({ detail: "尚未识别" }) } as Response;
        }
        if (url === "/api/v1/questions/question-1/recognize" && init?.method === "POST") {
          return {
            ok: true,
            json: async () => ({
              id: "recognition-1",
              provider_config_id: "provider-1",
              model_name: "vision-model",
              prompt_version: "recognition-v1",
              status: "succeeded",
              recognized_text: "题目右侧条件可能缺失",
              question_completeness: "partial",
              confidence: "low",
              warnings: ["题目右侧可能被裁切"],
              missing_information: ["右侧条件"],
              detected_subject: "初中数学",
              detected_grade: null,
              has_formula: false,
              has_diagram: false,
              duration_ms: 10,
            }),
          } as Response;
        }
        if (url === "/api/v1/questions/question-1/confirm" && init?.method === "POST") {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          confirmation = {
            ...body,
            id: "confirmation-1",
            question_id: "question-1",
            confirmed_text_hash: "hash",
          };
          return { ok: true, json: async () => confirmation } as Response;
        }
        if (url === "/api/v1/questions/question-1" && init?.method === "DELETE") {
          questions.delete("question-1");
          return { ok: true, status: 204 } as Response;
        }
        if (url === "/api/v1/questions/question-1/analysis" && (!init?.method || init.method === "GET")) {
          return { ok: false, status: 404, json: async () => ({ detail: "尚未分析" }) } as Response;
        }
        if (url === "/api/v1/questions/question-1/analyze" && init?.method === "POST") {
          analyzed = true;
          return {
            ok: true,
            json: async () => ({
              id: "analysis-1",
              provider_config_id: "provider-1",
              model_name: "text-model",
              prompt_version: "analysis-v1",
              schema_version: "analysis-schema-v1",
              status: "completed",
              subject: "小学数学",
              grade: "三年级",
              normalized_question: "计算 $2+3$ 的值。",
              question_completeness: "complete",
              knowledge_points: ["整数加法"],
              difficulty: "basic",
              final_answer: "$5$",
              solution_overview: "将两个加数相加。",
              solution_steps: [{ step: 1, content: "$2+3=5$。", reason: "按照整数加法规则计算。", knowledge_used: "整数加法" }],
              possible_mistakes: ["可能把加法符号误看成乘法符号"],
              memory_tip: "看清运算符号再计算。",
              next_time_checklist: ["看运算符", "按顺序计算", "检查结果"],
              confidence: "high",
              missing_information: [],
              verification: { status: "verified", message: "简单算术校验通过：结果为 5。" },
              duration_ms: 20,
              created_at: "2026-07-21T00:00:00Z",
            }),
          } as Response;
        }
        if (url === "/api/v1/questions/question-1/learning" && (!init?.method || init.method === "GET")) {
          return { ok: true, json: async () => learning } as Response;
        }
        if (url === "/api/v1/questions/question-1/learning" && init?.method === "PUT") {
          learning = { ...learning, ...JSON.parse(init.body as string) };
          return { ok: true, json: async () => learning } as Response;
        }
        if (url === "/api/v1/questions/question-1/variations" && (!init?.method || init.method === "GET")) {
          if (!variantsGenerated) return { ok: false, status: 404, json: async () => ({ detail: "尚未生成" }) } as Response;
          return { ok: true, json: async () => variationResult() } as Response;
        }
        if (url === "/api/v1/questions/question-1/variations" && init?.method === "POST") {
          variantsGenerated = true;
          return { ok: true, json: async () => variationResult() } as Response;
        }
        if (url.startsWith("/api/v1/notebook")) {
          const items = analyzed ? [{
            question_id: "question-1", question: "计算 $2+3$ 的值。", subject: "小学数学", grade: "三年级",
            knowledge_points: ["整数加法"], difficulty: "basic", actual_error_reason: learning.actual_error_reason,
            actual_error_note: learning.actual_error_note, mastery_status: learning.mastery_status, starred: learning.starred,
            review_count: 0, next_review_at: learning.next_review_at, created_at: "2026-07-21T00:00:00Z", updated_at: learning.updated_at,
          }] : [];
          return { ok: true, json: async () => ({ items, facets: { subjects: analyzed ? ["小学数学"] : [], knowledge_points: analyzed ? ["整数加法"] : [], total: items.length, new_count: items.length, reviewing_count: 0, mastered_count: 0 } }) } as Response;
        }
        if (url === "/api/v1/review/due") {
          return { ok: true, json: async () => [] } as Response;
        }
        if (url === "/api/v1/data/restore" && init?.method === "POST") {
          return { ok: true, json: async () => ({ accepted: true, requires_restart: true, message: "备份已验证。请重新启动工作台。" }) } as Response;
        }
        throw new Error(`未模拟的请求：${url}`);
      }),
    );
  });

  it("以中文展示工作台核心入口和模型缺失说明", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "把错题变成真正掌握的知识" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "上传题目图片" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "直接输入题目" })).toBeInTheDocument();
    expect(screen.getByText(/所有学习记录默认保存在本机/)).toBeInTheDocument();
    expect(await screen.findByText(/未配置视觉模型/)).toBeInTheDocument();
  });

  it("显示本地后端连接状态", async () => {
    render(<App />);

    expect(await screen.findByText("本地服务已连接")).toBeInTheDocument();
  });

  it("创建文字题目后必须进入确认页", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "直接输入题目" }));
    await user.type(screen.getByLabelText("题目文字"), "解方程 x + 2 = 5");
    await user.click(screen.getByRole("button", { name: "保存文字题目" }));

    expect(await screen.findByRole("heading", { name: "确认题目文字" })).toBeInTheDocument();
    expect(screen.getByLabelText("识别出的题目文字")).toHaveValue("解方程 x + 2 = 5");
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/questions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ input_type: "text", source_text: "解方程 x + 2 = 5" }),
      }),
    );
  });

  it("可以在设置页保存并测试模型配置", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "设置" }));
    expect(await screen.findByLabelText("超时时间（秒）")).toHaveValue(600);
    expect(screen.getByText(/文本模型建议设置 600 秒/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("配置名称"), "DeepSeek 文本模型");
    await user.type(screen.getByLabelText("Base URL"), "https://api.example.test/v1");
    await user.type(screen.getByLabelText("API Key"), "secret-key");
    await user.type(screen.getByLabelText("模型名称"), "deepseek-chat");
    await user.click(screen.getByRole("button", { name: "保存模型配置" }));

    expect(await screen.findByText("DeepSeek 文本模型")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "测试 DeepSeek 文本模型" }));
    expect(await screen.findByText("连接成功，已找到配置的模型。")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("secret-key")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载完整备份" })).toHaveAttribute("href", "/api/v1/data/backup");

    await user.upload(screen.getByLabelText("选择备份文件"), new File(["backup"], "backup.zip", { type: "application/zip" }));
    expect(await screen.findByText("备份已验证。请重新启动工作台。")).toBeInTheDocument();
  });

  it("只有明确勾选完整性后才能确认题目", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "直接输入题目" }));
    await user.type(screen.getByLabelText("题目文字"), "求 2 + 3 的值");
    await user.click(screen.getByRole("button", { name: "保存文字题目" }));
    const confirmButton = await screen.findByRole("button", { name: "确认题目" });
    expect(confirmButton).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /我已确认题目文字和条件完整/ }));
    await user.click(confirmButton);
    expect(await screen.findByText("题目已确认")).toBeInTheDocument();
  });

  it("确认题目后可以生成并阅读结构化分析", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "设置" }));
    await user.type(await screen.findByLabelText("配置名称"), "文本模型");
    await user.type(screen.getByLabelText("Base URL"), "https://text.example.test/v1");
    await user.type(screen.getByLabelText("API Key"), "text-key");
    await user.type(screen.getByLabelText("模型名称"), "text-model");
    await user.click(screen.getByRole("button", { name: "保存模型配置" }));
    await screen.findByText("文本模型");
    await user.click(screen.getByRole("link", { name: "首页" }));

    await user.click(screen.getByRole("button", { name: "直接输入题目" }));
    await user.type(screen.getByLabelText("题目文字"), "计算 2 + 3 的值");
    await user.click(screen.getByRole("button", { name: "保存文字题目" }));
    await user.click(await screen.findByRole("checkbox", { name: /我已确认题目文字和条件完整/ }));
    await user.click(screen.getByRole("button", { name: "确认题目" }));
    await user.click(await screen.findByRole("link", { name: "开始分析" }));

    expect(
      await screen.findByRole("heading", { name: "错题复盘" }, { timeout: 5_000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "正确答案" })).toBeInTheDocument();
    expect(screen.getByText("可能把加法符号误看成乘法符号")).toBeInTheDocument();
    expect(screen.getByText("简单算术校验通过：结果为 5。")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "计算出错" }));
    await user.type(screen.getByPlaceholderText(/进位时忘记加一/), "我把加号看错了");
    await user.click(screen.getByRole("button", { name: "保存真实错因" }));
    expect(await screen.findByText("已保存到错题本")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "生成变式题" }));
    expect(await screen.findByRole("heading", { name: "同知识点巩固" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "换场景迁移" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "提高难度" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "错题本" }));
    expect(await screen.findByRole("heading", { name: "我的错题本" })).toBeInTheDocument();
    expect(await screen.findByText(/我把加号看错了/)).toBeInTheDocument();
  });

  it("低可信度识别结果必须显示不完整警告", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("link", { name: "设置" }));
    await user.selectOptions(screen.getByLabelText("用途"), "vision");
    await user.type(await screen.findByLabelText("配置名称"), "视觉模型");
    await user.type(screen.getByLabelText("Base URL"), "https://vision.example.test/v1");
    await user.type(screen.getByLabelText("API Key"), "vision-key");
    await user.type(screen.getByLabelText("模型名称"), "vision-model");
    await user.click(screen.getByRole("button", { name: "保存模型配置" }));
    await screen.findByText("视觉模型");
    await user.click(screen.getByRole("link", { name: "首页" }));

    const file = new File(["png-content"], "题目.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("选择题目图片"), file);
    await user.click(screen.getByRole("button", { name: "保存题目图片" }));

    expect(await screen.findByText(/题目识别可能不完整，请检查或手动修改后再分析/)).toBeInTheDocument();
    expect(screen.getByLabelText("识别出的题目文字")).toHaveValue("题目右侧条件可能缺失");
    expect(screen.getByRole("checkbox", { name: /我已确认题目文字和条件完整/ })).not.toBeChecked();
  });

  it("上传图片后进入确认页并提示视觉模型缺失", async () => {
    const user = userEvent.setup();
    render(<App />);
    const file = new File(["png-content"], "题目.png", { type: "image/png" });

    await user.upload(screen.getByLabelText("选择题目图片"), file);
    await user.click(screen.getByRole("button", { name: "保存题目图片" }));

    expect(await screen.findByRole("heading", { name: "确认题目文字" })).toBeInTheDocument();
    expect(screen.getByAltText("原始题目图片")).toHaveAttribute(
      "src",
      "/api/v1/questions/question-1/image",
    );
    expect(screen.getByText(/未配置视觉模型，无法自动读取图片/)).toBeInTheDocument();
  });
});
