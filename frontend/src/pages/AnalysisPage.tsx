import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AnalysisResult, analyzeQuestion, getAnalysis } from "../api/analysis";
import { listProviders } from "../api/providers";
import { LearningLoop } from "../components/LearningLoop";
import { MarkdownContent } from "../components/MarkdownContent";

const DIFFICULTY = { basic: "基础", medium: "中等", hard: "较难" } as const;
const CONFIDENCE = { high: "较高", medium: "中等", low: "较低" } as const;

export function AnalysisPage() {
  const { id = "" } = useParams();
  const savedAnalysis = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => getAnalysis(id),
  });
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const textProviders = useMemo(
    () => providers.data?.filter((item) => item.capability === "text" && item.enabled) ?? [],
    [providers.data],
  );
  const [providerId, setProviderId] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoStarted = useRef(false);

  useEffect(() => {
    if (savedAnalysis.data) setAnalysis(savedAnalysis.data);
  }, [savedAnalysis.data]);

  useEffect(() => {
    if (!providerId && textProviders[0]) setProviderId(textProviders[0].id);
  }, [providerId, textProviders]);

  async function runAnalysis() {
    setAnalyzing(true);
    setError(null);
    try {
      setAnalysis(await analyzeQuestion(id, providerId || undefined));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "错题分析失败。");
    } finally {
      setAnalyzing(false);
    }
  }

  useEffect(() => {
    const shouldStart =
      savedAnalysis.isSuccess &&
      savedAnalysis.data === null &&
      Boolean(providerId) &&
      !autoStarted.current;
    if (shouldStart) {
      autoStarted.current = true;
      void runAnalysis();
    }
  });

  if (savedAnalysis.isPending || providers.isPending) {
    return (
      <main className="page-shell analysis-loading">
        <div className="analysis-pulse" />
        <h1>正在准备错题复盘</h1>
        <p>先核对确认记录，再调用你配置的文本模型。</p>
      </main>
    );
  }

  if (providers.isSuccess && textProviders.length === 0) {
    return (
      <main className="page-shell narrow-page">
        <div className="eyebrow">缺少文本模型</div>
        <h1>暂时不能开始分析</h1>
        <div className="panel missing-provider-panel">
          <p>题目已经确认，但尚未配置可用的文本分析模型。</p>
          <Link className="primary-action" to="/settings">前往设置文本模型</Link>
        </div>
      </main>
    );
  }

  if (analyzing && !analysis) {
    return (
      <main className="page-shell analysis-loading">
        <div className="analysis-pulse" />
        <div className="eyebrow">AI ANALYSIS</div>
        <h1>正在生成结构化复盘</h1>
        <p>检查题目信息、知识点与解题步骤，请不要关闭页面。</p>
      </main>
    );
  }

  if (error && !analysis) {
    return (
      <main className="page-shell narrow-page">
        <div className="eyebrow">分析未完成</div>
        <h1>无法生成可靠结果</h1>
        <div className="form-message is-error">{error}</div>
        <div className="error-actions">
          <Link className="secondary-action" to={`/questions/${id}/confirm`}>返回确认页</Link>
          <button className="primary-action" type="button" onClick={runAnalysis}>重新分析</button>
        </div>
      </main>
    );
  }

  if (!analysis) return null;

  if (analysis.status === "needs_more_information") {
    return (
      <main className="page-shell narrow-page information-shortage">
        <div className="eyebrow">信息完整性检查</div>
        <h1>信息不足，无法可靠分析</h1>
        <section className="panel">
          <p>为了避免编造答案，系统已经停止分析。请补充以下信息：</p>
          <ul>{analysis.missing_information.map((item) => <li key={item}>{item}</li>)}</ul>
          <Link className="primary-action" to={`/questions/${id}/confirm`}>返回修改题目</Link>
        </section>
        <AiNotice />
      </main>
    );
  }

  const verificationClass = analysis.verification.status === "conflict" ? "conflict" : "verified";

  return (
    <main className="page-shell analysis-page">
      <header className="analysis-header">
        <div>
          <div className="eyebrow">第 2 步 · 理解与复盘</div>
          <h1>错题复盘</h1>
          <div className="analysis-tags">
            <span>{analysis.subject || "未分类学科"}</span>
            {analysis.grade && <span>{analysis.grade}</span>}
            <span>{DIFFICULTY[analysis.difficulty]}</span>
            <span>可信度 {CONFIDENCE[analysis.confidence]}</span>
          </div>
        </div>
        <div className="analysis-header-actions">
          {textProviders.length > 1 && (
            <select aria-label="文本分析模型" value={providerId} onChange={(event) => setProviderId(event.target.value)}>
              {textProviders.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
            </select>
          )}
          <button className="secondary-action" type="button" disabled={analyzing} onClick={runAnalysis}>
            {analyzing ? "正在分析…" : "重新分析"}
          </button>
        </div>
      </header>

      <section className="analysis-question paper-section">
        <span className="paper-index">01</span>
        <div><SectionTitle kicker="QUESTION" title="题目整理" /><MarkdownContent>{analysis.normalized_question}</MarkdownContent></div>
      </section>

      <section className="knowledge-strip">
        <strong>核心知识点</strong>
        <div>{analysis.knowledge_points.map((point) => <span key={point}>{point}</span>)}</div>
      </section>

      <div className="analysis-two-column">
        <section className="answer-card paper-section">
          <span className="paper-index">02</span>
          <div><SectionTitle kicker="ANSWER" title="正确答案" /><MarkdownContent>{analysis.final_answer}</MarkdownContent></div>
        </section>
        <section className={`verification-card ${verificationClass}`}>
          <strong>{analysis.verification.status === "conflict" ? "自动校验发现不一致" : "确定性校验"}</strong>
          <p>{analysis.verification.message}</p>
        </section>
      </div>

      <section className="paper-section overview-section">
        <span className="paper-index">03</span>
        <div><SectionTitle kicker="APPROACH" title="整体解题思路" /><MarkdownContent>{analysis.solution_overview}</MarkdownContent></div>
      </section>

      <section className="steps-section">
        <SectionTitle kicker="STEP BY STEP" title="详细步骤" />
        <div className="solution-timeline">
          {analysis.solution_steps.map((step) => (
            <article key={step.step} className="solution-step">
              <span className="step-number">{String(step.step).padStart(2, "0")}</span>
              <div className="step-body">
                <MarkdownContent>{step.content}</MarkdownContent>
                <p><strong>为什么：</strong>{step.reason}</p>
                <span className="knowledge-used">使用知识：{step.knowledge_used}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="reflection-grid">
        <section className="reflection-card mistakes-card">
          <SectionTitle kicker="POSSIBLE MISTAKES" title="可能的错因包括" />
          <ul>{analysis.possible_mistakes.map((item) => <li key={item}>{item}</li>)}</ul>
          <p>以上是 AI 给出的候选错因，不代表你的真实思考过程。</p>
        </section>
        <section className="reflection-card memory-card">
          <SectionTitle kicker="MEMORY TIP" title="一句话记忆" />
          <blockquote>{analysis.memory_tip}</blockquote>
        </section>
      </div>

      <section className="checklist-section">
        <SectionTitle kicker="NEXT TIME" title="下次遇到类似题" />
        <ol>{analysis.next_time_checklist.map((item, index) => <li key={item}><span>{index + 1}</span>{item}</li>)}</ol>
      </section>

      <LearningLoop questionId={id} providerId={providerId || undefined} />

      <div className="analysis-metadata">
        模型：{analysis.model_name} · 提示词：{analysis.prompt_version} · Schema：{analysis.schema_version} · 用时：{analysis.duration_ms} ms
      </div>
      <AiNotice />
    </main>
  );
}

function SectionTitle({ kicker, title }: { kicker: string; title: string }) {
  return <div className="analysis-section-title"><span>{kicker}</span><h2>{title}</h2></div>;
}

function AiNotice() {
  return <aside className="ai-notice">AI 内容可能存在错误，请结合教材或老师讲解核对。</aside>;
}
