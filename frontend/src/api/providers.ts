export type ProviderConfig = {
  id: string;
  capability: "vision" | "text";
  provider_type: "openai_compatible" | "gemini";
  display_name: string;
  base_url: string;
  model_name: string;
  timeout_seconds: number;
  enabled: boolean;
  has_api_key: boolean;
  api_key_masked: string;
  last_test_status: "success" | "failed" | null;
  last_tested_at: string | null;
};

export type ProviderInput = {
  capability: "vision" | "text";
  provider_type: "openai_compatible" | "gemini";
  display_name: string;
  base_url: string;
  api_key: string;
  model_name: string;
  timeout_seconds: number;
  enabled: boolean;
};

export type ConnectionResult = {
  success: boolean;
  message: string;
  latency_ms: number;
};

async function requestError(response: Response): Promise<Error> {
  try {
    const data = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
    if (typeof data.detail === "string") return new Error(data.detail);
    return new Error(data.detail?.[0]?.msg || "配置保存失败，请检查填写内容。");
  } catch {
    return new Error("无法连接本地服务，请稍后重试。");
  }
}

export async function listProviders(): Promise<ProviderConfig[]> {
  const response = await fetch("/api/v1/providers");
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<ProviderConfig[]>;
}

export async function createProvider(input: ProviderInput): Promise<ProviderConfig> {
  const response = await fetch("/api/v1/providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<ProviderConfig>;
}

export async function updateProvider(
  id: string,
  input: Omit<ProviderInput, "capability" | "provider_type" | "api_key"> & { api_key?: string },
): Promise<ProviderConfig> {
  const response = await fetch(`/api/v1/providers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<ProviderConfig>;
}

export async function testProvider(id: string): Promise<ConnectionResult> {
  const response = await fetch(`/api/v1/providers/${id}/test`, { method: "POST" });
  if (!response.ok) throw await requestError(response);
  return response.json() as Promise<ConnectionResult>;
}

export async function deleteProvider(id: string): Promise<void> {
  const response = await fetch(`/api/v1/providers/${id}`, { method: "DELETE" });
  if (!response.ok) throw await requestError(response);
}
