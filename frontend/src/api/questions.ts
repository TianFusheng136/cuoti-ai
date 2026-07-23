type QuestionDraft = {
  id: string;
  status: "draft";
};

async function responseError(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string };
    return new Error(body.detail || "操作失败，请稍后重试。");
  } catch {
    return new Error("操作失败，请检查本地服务是否正常运行。");
  }
}

export async function createTextQuestion(sourceText: string): Promise<QuestionDraft> {
  const response = await fetch("/api/v1/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_type: "text", source_text: sourceText }),
  });
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<QuestionDraft>;
}

export async function deleteQuestion(id: string): Promise<void> {
  const response = await fetch(`/api/v1/questions/${id}`, { method: "DELETE" });
  if (!response.ok) throw await responseError(response);
}

export async function createImageQuestion(
  file: File,
  inputType: "image" | "clipboard",
): Promise<QuestionDraft> {
  const draftResponse = await fetch("/api/v1/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_type: inputType }),
  });
  if (!draftResponse.ok) throw await responseError(draftResponse);
  const draft = (await draftResponse.json()) as QuestionDraft;

  const form = new FormData();
  form.append("file", file);
  const uploadResponse = await fetch(`/api/v1/questions/${draft.id}/image`, {
    method: "POST",
    body: form,
  });
  if (!uploadResponse.ok) {
    await fetch(`/api/v1/questions/${draft.id}`, { method: "DELETE" }).catch(() => undefined);
    throw await responseError(uploadResponse);
  }
  return draft;
}
