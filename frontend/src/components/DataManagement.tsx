import { ChangeEvent, useState } from "react";

import { restoreBackup } from "../api/data";

export function DataManagement() {
  const [restoring, setRestoring] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function selectBackup(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!window.confirm("恢复将在下次启动时替换当前题目和学习记录。确定继续吗？")) return;
    setRestoring(true);
    setMessage(null);
    setError(null);
    try {
      const result = await restoreBackup(file);
      setMessage(result.message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "备份恢复失败。");
    } finally {
      setRestoring(false);
    }
  }

  return (
    <section className="panel data-management" aria-labelledby="data-management-title">
      <div className="panel-heading">
        <div><span className="section-kicker">LOCAL DATA</span><h2 id="data-management-title">备份与导出</h2></div>
      </div>
      <p>完整备份包含题目、图片和复习记录，但默认且始终不包含 API Key。</p>
      <div className="data-actions">
        <a className="primary-action" href="/api/v1/data/backup" download>下载完整备份</a>
        <label className={`secondary-action file-action ${restoring ? "is-disabled" : ""}`}>
          {restoring ? "正在验证…" : "从备份恢复"}
          <input aria-label="选择备份文件" type="file" accept=".zip,application/zip" disabled={restoring} onChange={selectBackup} />
        </label>
      </div>
      <div className="export-actions">
        <span>只导出错题本：</span>
        <a href="/api/v1/data/export?format=json" download>JSON</a>
        <a href="/api/v1/data/export?format=csv" download>CSV</a>
      </div>
      {message && <div className="form-message is-success" role="status">{message}</div>}
      {error && <div className="form-message is-error" role="alert">{error}</div>}
      <small>恢复后需要使用 stop.bat 停止，再通过 start.bat 启动。模型配置会保留，但必须重新填写 API Key。</small>
    </section>
  );
}
