export type ErrorReason =
  | "concept"
  | "calculation"
  | "reading"
  | "method"
  | "careless"
  | "other"
  | "unknown";
export type MasteryStatus = "new" | "reviewing" | "mastered";

export type LearningRecord = {
  question_id: string;
  actual_error_reason: ErrorReason | null;
  actual_error_note: string | null;
  mastery_status: MasteryStatus;
  starred: boolean;
  review_count: number;
  next_review_at: string | null;
  last_reviewed_at: string | null;
  updated_at: string;
};

export type Variation = {
  type: "same_point" | "new_context" | "challenge";
  title: string;
  question: string;
  answer: string;
  solution: string;
  knowledge_points: string[];
  difficulty: "basic" | "medium" | "hard";
};

export type VariationResult = {
  id: string;
  provider_config_id: string | null;
  model_name: string;
  prompt_version: string;
  schema_version: string;
  variants: Variation[];
  duration_ms: number;
  created_at: string;
};

export type NotebookItem = {
  question_id: string;
  question: string;
  subject: string;
  grade: string;
  knowledge_points: string[];
  difficulty: string;
  actual_error_reason: ErrorReason | null;
  actual_error_note: string | null;
  mastery_status: MasteryStatus;
  starred: boolean;
  review_count: number;
  next_review_at: string | null;
  created_at: string;
  updated_at: string;
};

export type NotebookResult = {
  items: NotebookItem[];
  facets: {
    subjects: string[];
    knowledge_points: string[];
    total: number;
    new_count: number;
    reviewing_count: number;
    mastered_count: number;
  };
};

async function errorFrom(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string };
    return new Error(body.detail || "操作失败，请稍后重试。");
  } catch {
    return new Error("无法连接本地服务。");
  }
}

export async function getLearning(questionId: string): Promise<LearningRecord> {
  const response = await fetch(`/api/v1/questions/${questionId}/learning`);
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<LearningRecord>;
}

export async function updateLearning(
  questionId: string,
  update: Partial<Pick<LearningRecord, "actual_error_reason" | "actual_error_note" | "mastery_status" | "starred">>,
): Promise<LearningRecord> {
  const response = await fetch(`/api/v1/questions/${questionId}/learning`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<LearningRecord>;
}

export async function getVariations(questionId: string): Promise<VariationResult | null> {
  const response = await fetch(`/api/v1/questions/${questionId}/variations`);
  if (response.status === 404) return null;
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<VariationResult>;
}

export async function generateVariations(
  questionId: string,
  providerId?: string,
): Promise<VariationResult> {
  const response = await fetch(`/api/v1/questions/${questionId}/variations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_id: providerId || null }),
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<VariationResult>;
}

export async function getNotebook(filters: {
  search?: string;
  subject?: string;
  knowledge?: string;
  mastery?: string;
  starred?: boolean;
} = {}): Promise<NotebookResult> {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const response = await fetch(`/api/v1/notebook${query.size ? `?${query}` : ""}`);
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<NotebookResult>;
}

export async function getDueReviews(): Promise<NotebookItem[]> {
  const response = await fetch("/api/v1/review/due");
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<NotebookItem[]>;
}

export async function recordReview(
  questionId: string,
  result: "remembered" | "forgotten",
): Promise<LearningRecord & { scheduled_days: number }> {
  const response = await fetch(`/api/v1/questions/${questionId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result }),
  });
  if (!response.ok) throw await errorFrom(response);
  return response.json() as Promise<LearningRecord & { scheduled_days: number }>;
}
