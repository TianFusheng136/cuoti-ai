export type RestoreResult = {
  accepted: boolean;
  requires_restart: boolean;
  message: string;
};

export async function restoreBackup(file: File): Promise<RestoreResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/v1/data/restore", { method: "POST", body: form });
  if (!response.ok) {
    let message = "备份恢复失败。";
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail || message;
    } catch {
      message = "无法读取备份文件。";
    }
    throw new Error(message);
  }
  return response.json() as Promise<RestoreResult>;
}
