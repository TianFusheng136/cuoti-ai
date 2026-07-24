import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { DataManagement } from "../components/DataManagement";
import {
  ConnectionResult,
  ProviderConfig,
  ProviderInput,
  createProvider,
  deleteProvider,
  listProviders,
  testProvider,
  updateProvider,
} from "../api/providers";

const EMPTY_FORM: ProviderInput = {
  capability: "text",
  provider_type: "openai_compatible",
  display_name: "",
  base_url: "",
  api_key: "",
  model_name: "",
  timeout_seconds: 600,
  enabled: true,
};

export function SettingsPage() {
  const queryClient = useQueryClient();
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const [form, setForm] = useState<ProviderInput>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ConnectionResult>>({});
  const [error, setError] = useState<string | null>(null);

  function updateForm<K extends keyof ProviderInput>(key: K, value: ProviderInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setError(null);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await updateProvider(editingId, {
          display_name: form.display_name,
          base_url: form.base_url,
          model_name: form.model_name,
          timeout_seconds: form.timeout_seconds,
          enabled: form.enabled,
          ...(form.api_key ? { api_key: form.api_key } : {}),
        });
      } else {
        await createProvider(form);
      }
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["providers"] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模型配置保存失败。");
    } finally {
      setSaving(false);
    }
  }

  function edit(provider: ProviderConfig) {
    setEditingId(provider.id);
    setError(null);
    setForm({
      capability: provider.capability,
      provider_type: provider.provider_type,
      display_name: provider.display_name,
      base_url: provider.base_url,
      api_key: "",
      model_name: provider.model_name,
      timeout_seconds: provider.timeout_seconds,
      enabled: provider.enabled,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function runTest(provider: ProviderConfig) {
    setTestingId(provider.id);
    setError(null);
    try {
      const result = await testProvider(provider.id);
      setResults((current) => ({ ...current, [provider.id]: result }));
      await queryClient.invalidateQueries({ queryKey: ["providers"] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模型连接测试失败。");
    } finally {
      setTestingId(null);
    }
  }

  async function remove(provider: ProviderConfig) {
    if (!window.confirm(`确定删除“${provider.display_name}”吗？`)) return;
    try {
      await deleteProvider(provider.id);
      await queryClient.invalidateQueries({ queryKey: ["providers"] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模型配置删除失败。");
    }
  }

  return (
    <main className="page-shell settings-page">
      <div className="settings-intro">
        <div><div className="eyebrow">本地配置</div><h1>设置</h1></div>
        <p>API Key 仅发送到本机后端，并使用当前 Windows 用户的 DPAPI 加密保存。</p>
      </div>

      <div className="settings-layout">
        <form className="panel provider-form" onSubmit={save}>
          <div className="panel-heading">
            <div><span className="section-kicker">MODEL SERVICE</span><h2>{editingId ? "编辑模型配置" : "添加模型配置"}</h2></div>
            {editingId && <button className="text-button" type="button" onClick={resetForm}>取消编辑</button>}
          </div>

          <div className="form-grid two-columns">
            <label>用途
              <select value={form.capability} disabled={Boolean(editingId)} onChange={(event) => updateForm("capability", event.target.value as ProviderInput["capability"])}>
                <option value="text">文本分析模型</option>
                <option value="vision">题目视觉识别模型</option>
              </select>
            </label>
            <label>接口类型
              <select value={form.provider_type} disabled={Boolean(editingId)} onChange={(event) => {
                const providerType = event.target.value as ProviderInput["provider_type"];
                setForm((current) => ({
                  ...current,
                  provider_type: providerType,
                  base_url: providerType === "gemini" && !current.base_url
                    ? "https://generativelanguage.googleapis.com/v1beta"
                    : current.base_url,
                }));
              }}>
                <option value="openai_compatible">OpenAI 兼容接口</option>
                <option value="gemini">Gemini 原生接口</option>
              </select>
            </label>
          </div>

          <label>配置名称
            <input required maxLength={100} value={form.display_name} onChange={(event) => updateForm("display_name", event.target.value)} placeholder="例如：DeepSeek 文本模型" />
          </label>
          <label>Base URL
            <input required value={form.base_url} onChange={(event) => updateForm("base_url", event.target.value)} placeholder="https://api.example.com/v1" spellCheck={false} />
          </label>
          <label>API Key
            <input required={!editingId} type="password" autoComplete="new-password" value={form.api_key} onChange={(event) => updateForm("api_key", event.target.value)} placeholder={editingId ? "留空表示不修改" : "只会加密保存在本机"} />
          </label>
          <div className="form-grid model-row">
            <label>模型名称
              <input required value={form.model_name} onChange={(event) => updateForm("model_name", event.target.value)} placeholder="请按服务商文档填写" spellCheck={false} />
            </label>
            <label>超时时间（秒）
              <input required type="number" min={5} max={600} value={form.timeout_seconds} onChange={(event) => updateForm("timeout_seconds", Number(event.target.value))} />
            </label>
          </div>
          <p className="provider-help">
            生成三类变式会连续设计和验算多次，文本模型建议设置 600 秒（10 分钟）。旧配置如果经常超时，请点“编辑”改为 600 秒。Base URL 和模型名称以服务商官方文档为准。
          </p>
          {error && <div className="form-message is-error" role="alert">{error}</div>}
          <button className="primary-action full-action" type="submit" disabled={saving}>
            {saving ? "正在保存…" : editingId ? "保存修改" : "保存模型配置"}
          </button>
        </form>

        <section className="provider-list" aria-labelledby="configured-providers">
          <div className="provider-list-heading">
            <div><span className="section-kicker">CONFIGURED</span><h2 id="configured-providers">已配置服务</h2></div>
            <span className="number-badge">{providers.data?.length ?? 0}</span>
          </div>

          {providers.isPending && <div className="empty-state">正在读取本地配置…</div>}
          {providers.isError && <div className="form-message is-error">无法读取模型配置。</div>}
          {providers.data?.length === 0 && <div className="empty-state">尚未配置模型。只配置文本模型时，图片识别功能将不可用。</div>}
          {providers.data?.map((provider) => {
            const result = results[provider.id];
            return (
              <article className="provider-card" key={provider.id}>
                <div className="provider-card-title">
                  <div><span className={`capability-badge ${provider.capability}`}>{provider.capability === "vision" ? "视觉识别" : "文本分析"}</span><h3>{provider.display_name}</h3></div>
                  <span className={`connection-dot ${provider.last_test_status ?? "untested"}`} title="最近连接状态" />
                </div>
                <dl>
                  <div><dt>类型</dt><dd>{provider.provider_type === "gemini" ? "Gemini" : "OpenAI 兼容"}</dd></div>
                  <div><dt>模型</dt><dd>{provider.model_name}</dd></div>
                  <div><dt>密钥</dt><dd>{provider.api_key_masked}</dd></div>
                </dl>
                {result && <div className={`connection-result ${result.success ? "success" : "failed"}`}>{result.message}<small>{result.latency_ms} ms</small></div>}
                <div className="provider-actions">
                  <button type="button" className="secondary-action" onClick={() => edit(provider)}>编辑</button>
                  <button type="button" className="secondary-action danger-action" onClick={() => remove(provider)}>删除</button>
                  <button type="button" className="primary-action" aria-label={`测试 ${provider.display_name}`} disabled={testingId === provider.id} onClick={() => runTest(provider)}>
                    {testingId === provider.id ? "测试中…" : "测试连接"}
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      </div>

      <DataManagement />

      <aside className="privacy-note settings-privacy">
        <span aria-hidden="true">⌾</span>
        <p><strong>密钥安全说明</strong>页面不会重新读取 API Key 明文；导出和备份默认不包含密钥。更换 Windows 用户后需要重新填写。</p>
      </aside>
    </main>
  );
}
