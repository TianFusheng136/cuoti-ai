import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  ErrorReason,
  generateVariations,
  getLearning,
  getVariations,
  updateLearning,
} from "../api/learning";
import { MarkdownContent } from "./MarkdownContent";

const REASONS: Array<[ErrorReason, string]> = [
  ["concept", "概念没掌握"],
  ["calculation", "计算出错"],
  ["reading", "审题偏差"],
  ["method", "方法不会"],
  ["careless", "粗心遗漏"],
  ["other", "其他"],
];
const VARIANT_KICKERS = {
  same_point: "同知识点巩固",
  new_context: "换场景迁移",
  challenge: "提高难度",
} as const;

export function LearningLoop({ questionId, providerId }: { questionId: string; providerId?: string }) {
  const learningQuery = useQuery({
    queryKey: ["learning", questionId],
    queryFn: () => getLearning(questionId),
  });
  const variationQuery = useQuery({
    queryKey: ["variations", questionId],
    queryFn: () => getVariations(questionId),
  });
  const [reason, setReason] = useState<ErrorReason | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starring, setStarring] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (learningQuery.data) {
      setReason(learningQuery.data.actual_error_reason);
      setNote(learningQuery.data.actual_error_note ?? "");
    }
  }, [learningQuery.data]);

  async function saveReason() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const record = await updateLearning(questionId, {
        actual_error_reason: reason,
        actual_error_note: note.trim() || null,
      });
      setReason(record.actual_error_reason);
      setSaved(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "保存错因失败。");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStar() {
    if (!learningQuery.data) return;
    setStarring(true);
    setError(null);
    try {
      const record = await updateLearning(questionId, {
        starred: !learningQuery.data.starred,
      });
      await learningQuery.refetch();
      setSaved(Boolean(record));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "收藏状态更新失败。");
    } finally {
      setStarring(false);
    }
  }

  async function createVariants() {
    setGenerating(true);
    setError(null);
    try {
      await generateVariations(questionId, providerId);
      await variationQuery.refetch();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "变式题生成失败。");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="learning-loop">
      <section className="reason-section">
        <div className="analysis-section-title"><span>YOUR REFLECTION</span><h2>这次我真正错在哪里？</h2></div>
        <p className="section-help">AI 只能提供候选错因，最终原因由你自己确认。</p>
        <div className="reason-options" role="radiogroup" aria-label="真实错因">
          {REASONS.map(([value, label]) => (
            <button
              className={reason === value ? "is-selected" : ""}
              role="radio"
              aria-checked={reason === value}
              key={value}
              type="button"
              onClick={() => { setReason(value); setSaved(false); }}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="reason-note">
          <span>补充一句自己的思考（可选）</span>
          <textarea value={note} maxLength={2000} onChange={(event) => { setNote(event.target.value); setSaved(false); }} placeholder="例如：列式正确，但进位时忘记加一" />
        </label>
        <div className="reason-actions">
          <button className="secondary-action" type="button" disabled={starring} onClick={toggleStar}>
            {learningQuery.data?.starred ? "★ 已收藏" : "☆ 收藏到重点"}
          </button>
          {saved && <span role="status">已保存到错题本</span>}
          <button className="primary-action" type="button" disabled={saving || !reason} onClick={saveReason}>
            {saving ? "保存中…" : "保存真实错因"}
          </button>
        </div>
      </section>

      <section className="variants-section">
        <div className="variants-heading">
          <div className="analysis-section-title"><span>TRANSFER PRACTICE</span><h2>三类变式练习</h2></div>
          <button className="primary-action" type="button" disabled={generating} onClick={createVariants}>
            {generating ? "正在生成，请不要重复点击…" : variationQuery.data ? "重新生成" : "生成变式题"}
          </button>
        </div>
        <p className="section-help">通常需要 30 秒到 3 分钟，遇到定向重试可能更久。请等待生成和验算完成，不要重复点击。</p>
        {error && <div className="form-message is-error">{error}</div>}
        {variationQuery.data ? (
          <div className="variant-grid">
            {variationQuery.data.variants.map((variant, index) => (
              <article className="variant-card" key={`${variant.type}-${index}`}>
                <div className="variant-label"><span>0{index + 1}</span>{VARIANT_KICKERS[variant.type]}</div>
                <h3>{variant.title}</h3>
                <MarkdownContent>{variant.question}</MarkdownContent>
                <div className="variant-points">{variant.knowledge_points.map((point) => <span key={point}>{point}</span>)}</div>
                <details>
                  <summary>查看答案与解析</summary>
                  <strong>答案</strong><MarkdownContent>{variant.answer}</MarkdownContent>
                  <strong>解析</strong><MarkdownContent>{variant.solution}</MarkdownContent>
                </details>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">生成后会出现同知识点、换场景和提高难度三道练习。</div>
        )}
      </section>
    </div>
  );
}
