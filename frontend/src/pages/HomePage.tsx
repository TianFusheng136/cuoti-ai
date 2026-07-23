import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getDueReviews, getNotebook } from "../api/learning";
import { QuestionComposer } from "../components/QuestionComposer";

export function HomePage() {
  const notebook = useQuery({ queryKey: ["notebook-home"], queryFn: () => getNotebook() });
  const due = useQuery({ queryKey: ["due-reviews"], queryFn: getDueReviews });
  const recent = notebook.data?.items.slice(0, 3) ?? [];

  return (
    <main className="page-shell">
      <section className="hero" aria-labelledby="hero-title">
        <div className="eyebrow">今天，从一道错题开始</div>
        <h1 id="hero-title">把错题变成真正掌握的知识</h1>
        <p className="hero-copy">
          先确认题目，再理解知识点、错因与解题路径。AI 不会跳过你的确认直接作答。
        </p>

        <QuestionComposer />
        <p className="paste-tip">提示：复制截图后，可在此页面按 Ctrl + V 粘贴</p>
      </section>

      <section className="dashboard-grid" aria-label="学习概览">
        <article className="panel review-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">REVIEW</span><h2>今日待复习</h2></div>
            <span className="number-badge">{due.data?.length ?? 0}</span>
          </div>
          {due.data?.length ? <Link className="dashboard-entry" to="/review">有 {due.data.length} 道题等待复习 <span>开始 →</span></Link> : <div className="empty-state">今天没有到期错题。</div>}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div><span className="section-kicker">RECENT</span><h2>最近错题</h2></div>
            <Link className="text-button" to="/notebook">进入错题本 →</Link>
          </div>
          {recent.length ? <div className="recent-list">{recent.map((item) => <Link key={item.question_id} to={`/questions/${item.question_id}/analysis`}>{item.question}<span>{item.subject} · {item.knowledge_points[0]}</span></Link>)}</div> : <div className="empty-state">还没有错题记录。</div>}
        </article>

        <article className="panel knowledge-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">KNOWLEDGE</span><h2>知识点概览</h2></div>
          </div>
          {notebook.data?.facets.knowledge_points.length ? <div className="knowledge-cloud">{notebook.data.facets.knowledge_points.map((point) => <span key={point}>{point}</span>)}</div> : <div className="empty-state">知识点将在完成分析后自动整理。</div>}
        </article>
      </section>

      <aside className="privacy-note">
        <span aria-hidden="true">⌂</span>
        <p><strong>本地优先，隐私可控</strong>所有学习记录默认保存在本机；仅调用你配置的模型时，题目内容才会发送给对应服务商。</p>
      </aside>
    </main>
  );
}
