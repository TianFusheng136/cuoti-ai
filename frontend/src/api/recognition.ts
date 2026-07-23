export type QuestionAsset = {
  id: string;
  mime_type: string;
  width: number;
  height: number;
};

export type Question = {
  id: string;
  input_type: "text" | "image" | "clipboard";
  source_text: string | null;
  status: string;
  assets: QuestionAsset[];
};

export type RecognitionResult = {
  id: string;
  provider_config_id: string;
  model_name: string;
  prompt_version: string;
  status: "succeeded";
  recognized_text: string;
  question_completeness: "complete" | "partial" | "uncertain";
  confidence: "high" | "medium" | "low";
  warnings: string[];
  missing_information: string[];
  detected_subject: string | null;
  detected_grade: string | null;
  has_formula: boolean;
  has_diagram: boolean;
  duration_ms: number;
};

export type Confirmation = {
  id: string;
  question_id: string;
  confirmed_text: string;
  subject: string | null;
  grade: string | null;
  user_answer: string | null;
  user_solution: string | null;
};

export type ConfirmationInput = {
  confirmed_text: string;
  subject?: string;
  grade?: string;
  user_answer?: string;
  user_solution?: string;
  acknowledge_complete: true;
};

async function apiError(response: Response): Promise<Error> {
  try {
    const data = (await response.json()) as { detail?: string };
    return new Error(data.detail || "操作失败，请稍后重试。");
  } catch {
    return new Error("无法连接本地服务。");
  }
}

export async function getQuestion(id: string): Promise<Question> {
  const response = await fetch(`/api/v1/questions/${id}`);
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<Question>;
}

export async function getRecognition(id: string): Promise<RecognitionResult | null> {
  const response = await fetch(`/api/v1/questions/${id}/recognition`);
  if (response.status === 404) return null;
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<RecognitionResult>;
}

export async function getConfirmation(id: string): Promise<Confirmation | null> {
  const response = await fetch(`/api/v1/questions/${id}/confirmation`);
  if (response.status === 404) return null;
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<Confirmation>;
}

export async function recognizeQuestion(
  id: string,
  providerId?: string,
): Promise<RecognitionResult> {
  const response = await fetch(`/api/v1/questions/${id}/recognize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_id: providerId || null }),
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<RecognitionResult>;
}

export async function confirmQuestion(id: string, input: ConfirmationInput) {
  const response = await fetch(`/api/v1/questions/${id}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<Confirmation>;
}
