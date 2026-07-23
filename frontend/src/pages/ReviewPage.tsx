import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getDueReviews, recordReview } from "../api/learning";
import { MarkdownContent } from "../components/MarkdownContent";

export function ReviewPage() {
  const due = useQuery({ queryKey: ["due-reviews"], queryFn: getDueReviews });
  const [index, setIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const item = due.data?.[index];

  async function finish(result: "remembered" | "forgotten") {
    if (!item) return;
    setSaving(true);
    setError("");
    try {
      const updated = await recordReview(item.question_id, result);
      setMessage(result === "remembered" ? `已安排 ${updated.scheduled_days} 天后再次复习。` : "已加入明日复习，别着急。");
      setIndex((current) => current + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "复习记录保存失败。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page-shell review-page">
      <header className="review-header"><div><div className="eyebrow">SPACED REVIEW</div><h1>今日复习</h1><p>不要求一次完美，诚实判断是否想得起来。</p></div><span>{Math.min(index, due.data?.length ?? 0)} / {due.data?.length ?? 0}</span></header>
      {error && <div className="form-message is-error" role="alert">{error}</div>}
      {due.isError && <div className="form-message is-error" role="alert">复习列表读取失败，请稍后重试。</div>}
      {due.isPending ? <div className="empty-state">正在整理今日复习…</div> : item ? (
        <article className="review-card">
          <div className="review-card-meta"><span>{item.subject}</span>{item.knowledge_points.map((point) => <span key={point}>{point}</span>)}</div>
          <MarkdownContent>{item.question}</MarkdownContent>
          <p>先在纸上完整作答，再打开原复盘核对。</p>
          <Link className="secondary-action" to={`/questions/${item.question_id}/analysis`}>打开原复盘核对</Link>
          <div className="review-decisions">
            <button type="button" disabled={saving} onClick={() => finish("forgotten")}>还没想起来</button>
            <button className="primary-action" type="button" disabled={saving} onClick={() => finish("remembered")}>我记得方法</button>
          </div>
        </article>
      ) : (
        <section className="review-complete">
          <div aria-hidden="true">✓</div><h2>今天的复习完成了</h2><p>{message || "当前没有到期错题，可以录入一道新题。"}</p><Link className="primary-action" to="/notebook">返回错题本</Link>
        </section>
      )}
    </main>
  );
}
