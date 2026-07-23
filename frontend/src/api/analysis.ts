export type SolutionStep = {
  step: number;
  content: string;
  reason: string;
  knowledge_used: string;
};

export type AnalysisResult = {
  id: string;
  provider_config_id: string | null;
  model_name: string;
  prompt_version: string;
  schema_version: string;
  status: "completed" | "needs_more_information";
  subject: string;
  grade: string;
  normalized_question: string;
  question_completeness: "complete" | "partial" | "uncertain";
  knowledge_points: string[];
  difficulty: "basic" | "medium" | "hard";
  final_answer: string;
  solution_overview: string;
  solution_steps: SolutionStep[];
  possible_mistakes: string[];
  memory_tip: string;
  next_time_checklist: string[];
  confidence: "high" | "medium" | "low";
  missing_information: string[];
  verification: {
    status: "verified" | "conflict" | "not_applicable" | "verification_failed";
    message: string;
  };
  duration_ms: number;
  created_at: string;
};

async function apiError(response: Response): Promise<Error> {
  try {
    const data = (await response.json()) as { detail?: string };
    return new Error(data.detail || "分析失败，请稍后重试。");
  } catch {
    return new Error("无法连接本地服务。");
  }
}

export async function getAnalysis(id: string): Promise<AnalysisResult | null> {
  const response = await fetch(`/api/v1/questions/${id}/analysis`);
  if (response.status === 404) return null;
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<AnalysisResult>;
}

export async function analyzeQuestion(
  id: string,
  providerId?: string,
): Promise<AnalysisResult> {
  const response = await fetch(`/api/v1/questions/${id}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_id: providerId || null }),
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<AnalysisResult>;
}
