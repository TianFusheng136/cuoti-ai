import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { getNotebook, MasteryStatus, updateLearning } from "../api/learning";
import { deleteQuestion } from "../api/questions";
import { MarkdownContent } from "../components/MarkdownContent";

const REASON_LABEL: Record<string, string> = {
  concept: "概念没掌握", calculation: "计算出错", reading: "审题偏差",
  method: "方法不会", careless: "粗心遗漏", other: "其他", unknown: "暂未确认",
};
const STATUS_LABEL: Record<MasteryStatus, string> = {
  new: "待复习",
  reviewing: "复习中",
  mastered: "已掌握",
};

export function NotebookPage() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const [knowledge, setKnowledge] = useState("");
  const [mastery, setMastery] = useState("");
  const [starred, setStarred] = useState(false);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const filters = { search, subject, knowledge, mastery, starred: starred ? true : undefined };
  const notebook = useQuery({
    queryKey: ["notebook", filters],
    queryFn: () => getNotebook(filters),
  });

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearch(searchInput.trim());
  }

  async function toggleStar(questionId: string, current: boolean) {
    setWorkingId(questionId);
    setError(null);
    try {
      await updateLearning(questionId, { starred: !current });
      await notebook.refetch();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "收藏状态更新失败。");
    } finally {
      setWorkingId(null);
    }
  }

  async function removeQuestion(questionId: string) {
    if (!window.confirm("确定删除这道错题及其图片、分析和复习记录吗？")) return;
    setWorkingId(questionId);
    setError(null);
    try {
      await deleteQuestion(questionId);
      await notebook.refetch();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "删除错题失败。");
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <main className="page-shell notebook-page">
      <header className="notebook-header">
        <div><div className="eyebrow">LOCAL NOTEBOOK</div><h1>我的错题本</h1><p>按知识点整理，留下你真正的错因，而不是只收藏一道答案。</p></div>
        <Link className="primary-action" to="/">录入新错题</Link>
      </header>

      <section className="notebook-stats" aria-label="错题统计">
        <article><strong>{notebook.data?.facets.total ?? 0}</strong><span>全部错题</span></article>
        <article><strong>{notebook.data?.facets.new_count ?? 0}</strong><span>待复习</span></article>
        <article><strong>{notebook.data?.facets.reviewing_count ?? 0}</strong><span>复习中</span></article>
        <article><strong>{notebook.data?.facets.mastered_count ?? 0}</strong><span>已掌握</span></article>
      </section>

      <section className="notebook-filters" aria-label="错题筛选">
        <form onSubmit={submitSearch}>
          <label><span className="sr-only">搜索错题</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="搜索题目或知识点" /></label>
          <button className="secondary-action" type="submit">搜索</button>
        </form>
        <select aria-label="按学科筛选" value={subject} onChange={(event) => setSubject(event.target.value)}>
          <option value="">全部学科</option>
          {notebook.data?.facets.subjects.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select aria-label="按知识点筛选" value={knowledge} onChange={(event) => setKnowledge(event.target.value)}>
          <option value="">全部知识点</option>
          {notebook.data?.facets.knowledge_points.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select aria-label="按掌握状态筛选" value={mastery} onChange={(event) => setMastery(event.target.value)}>
          <option value="">全部状态</option><option value="new">待复习</option><option value="reviewing">复习中</option><option value="mastered">已掌握</option>
        </select>
        <label className="star-filter"><input type="checkbox" checked={starred} onChange={(event) => setStarred(event.target.checked)} />只看收藏</label>
      </section>

      {error && <div className="form-message is-error" role="alert">{error}</div>}
      {notebook.isError && <div className="form-message is-error" role="alert">错题本读取失败，请稍后重试。</div>}
      {notebook.isPending ? <div className="empty-state">正在读取本地错题本…</div> : notebook.data?.items.length ? (
        <div className="notebook-list">
          {notebook.data.items.map((item) => (
            <article className="notebook-card" key={item.question_id}>
              <div className="notebook-card-top">
                <div><span className={`mastery-badge ${item.mastery_status}`}>{STATUS_LABEL[item.mastery_status]}</span><span>{item.subject}</span><span>{item.grade}</span></div>
                <div className="notebook-card-actions">
                  <button
                    type="button"
                    aria-label={item.starred ? "取消收藏" : "收藏错题"}
                    disabled={workingId === item.question_id}
                    onClick={() => toggleStar(item.question_id, item.starred)}
                  >{item.starred ? "★" : "☆"}</button>
                  <button
                    type="button"
                    className="delete-question-button"
                    aria-label="删除错题"
                    disabled={workingId === item.question_id}
                    onClick={() => removeQuestion(item.question_id)}
                  >删除</button>
                </div>
              </div>
              <MarkdownContent>{item.question}</MarkdownContent>
              <div className="notebook-points">{item.knowledge_points.map((point) => <span key={point}>{point}</span>)}</div>
              {item.actual_error_reason && <p className="actual-reason-note"><strong>我的错因：</strong>{REASON_LABEL[item.actual_error_reason]}{item.actual_error_note ? ` · ${item.actual_error_note}` : ""}</p>}
              <Link to={`/questions/${item.question_id}/analysis`}>打开复盘 →</Link>
            </article>
          ))}
        </div>
      ) : <div className="empty-state notebook-empty">没有符合条件的错题。</div>}
    </main>
  );
}
