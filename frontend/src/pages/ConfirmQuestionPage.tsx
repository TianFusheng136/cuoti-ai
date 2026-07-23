import { useQuery } from "@tanstack/react-query";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listProviders } from "../api/providers";
import {
  RecognitionResult,
  confirmQuestion,
  getConfirmation,
  getQuestion,
  getRecognition,
  recognizeQuestion,
} from "../api/recognition";

const CONFIDENCE_LABELS = { high: "较高", medium: "中等", low: "较低" } as const;

export function ConfirmQuestionPage() {
  const { id = "" } = useParams();
  const question = useQuery({ queryKey: ["question", id], queryFn: () => getQuestion(id) });
  const savedRecognition = useQuery({
    queryKey: ["recognition", id],
    queryFn: () => getRecognition(id),
  });
  const savedConfirmation = useQuery({
    queryKey: ["confirmation", id],
    queryFn: () => getConfirmation(id),
  });
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const visionProviders = useMemo(
    () => providers.data?.filter((item) => item.capability === "vision" && item.enabled) ?? [],
    [providers.data],
  );
  const [recognition, setRecognition] = useState<RecognitionResult | null>(null);
  const [confirmedText, setConfirmedText] = useState("");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [userAnswer, setUserAnswer] = useState("");
  const [userSolution, setUserSolution] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [recognizing, setRecognizing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [providerId, setProviderId] = useState("");
  const autoRecognitionStarted = useRef(false);

  useEffect(() => {
    if (savedRecognition.data) setRecognition(savedRecognition.data);
  }, [savedRecognition.data]);

  useEffect(() => {
    if (
      initialized ||
      question.isPending ||
      savedRecognition.isPending ||
      savedConfirmation.isPending
    ) return;
    const confirmation = savedConfirmation.data;
    const result = savedRecognition.data;
    setConfirmedText(
      confirmation?.confirmed_text || result?.recognized_text || question.data?.source_text || "",
    );
    setSubject(confirmation?.subject || result?.detected_subject || "");
    setGrade(confirmation?.grade || result?.detected_grade || "");
    setUserAnswer(confirmation?.user_answer || "");
    setUserSolution(confirmation?.user_solution || "");
    setInitialized(true);
  }, [
    initialized,
    question.data,
    question.isPending,
    savedConfirmation.data,
    savedConfirmation.isPending,
    savedRecognition.data,
    savedRecognition.isPending,
  ]);

  useEffect(() => {
    if (!providerId && visionProviders[0]) setProviderId(visionProviders[0].id);
  }, [providerId, visionProviders]);

  async function runRecognition() {
    setRecognizing(true);
    setError(null);
    setSaved(false);
    try {
      const result = await recognizeQuestion(id, providerId || undefined);
      setRecognition(result);
      setConfirmedText(result.recognized_text);
      setSubject(result.detected_subject || "");
      setGrade(result.detected_grade || "");
      setAcknowledged(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "题目识别失败。");
    } finally {
      setRecognizing(false);
    }
  }

  useEffect(() => {
    const shouldRecognize =
      question.data?.input_type !== "text" &&
      savedRecognition.isSuccess &&
      savedRecognition.data === null &&
      Boolean(providerId) &&
      !autoRecognitionStarted.current;
    if (shouldRecognize) {
      autoRecognitionStarted.current = true;
      void runRecognition();
    }
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!acknowledged) {
      setError("请先确认题目文字和条件完整。 ");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await confirmQuestion(id, {
        confirmed_text: confirmedText,
        ...(subject.trim() ? { subject: subject.trim() } : {}),
        ...(grade.trim() ? { grade: grade.trim() } : {}),
        ...(userAnswer.trim() ? { user_answer: userAnswer.trim() } : {}),
        ...(userSolution.trim() ? { user_solution: userSolution.trim() } : {}),
        acknowledge_complete: true,
      });
      await savedConfirmation.refetch();
      setSaved(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "题目确认失败。");
    } finally {
      setSaving(false);
    }
  }

  if (question.isPending) return <main className="page-shell"><div className="empty-state">正在读取题目…</div></main>;
  if (question.isError || !question.data) return <main className="page-shell"><div className="form-message is-error">无法读取题目，请返回首页重试。</div></main>;

  const isImage = question.data.input_type !== "text";
  const risky = recognition && recognition.question_completeness !== "complete";

  return (
    <main className="page-shell confirm-page">
      <div className="confirm-header">
        <div><div className="eyebrow">第 1 步 · 核对原题</div><h1>确认题目文字</h1></div>
        <Link className="secondary-action" to="/">返回首页</Link>
      </div>

      <div className="confirm-layout">
        <section className="question-original panel" aria-labelledby="original-title">
          <div className="panel-heading"><div><span className="section-kicker">ORIGINAL</span><h2 id="original-title">原始题目</h2></div></div>
          {isImage ? (
            <img className="original-question-image" src={`/api/v1/questions/${id}/image`} alt="原始题目图片" />
          ) : (
            <div className="original-text-card">{question.data.source_text}</div>
          )}
          <p className="local-file-note">原始内容保存在本机，不会发送到项目作者服务器。</p>
        </section>

        <form className="question-confirm-form panel" onSubmit={submit}>
          <div className="recognition-toolbar">
            <div>
              <span className="section-kicker">RECOGNIZED TEXT</span>
              <h2>{isImage ? "识别与核对" : "核对题目"}</h2>
            </div>
            {isImage && (
              <div className="recognition-actions">
                {visionProviders.length > 1 && (
                  <select aria-label="视觉模型" value={providerId} onChange={(event) => setProviderId(event.target.value)}>
                    {visionProviders.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
                  </select>
                )}
                <button className="secondary-action" type="button" disabled={recognizing || visionProviders.length === 0} onClick={runRecognition}>
                  {recognizing ? "正在识别…" : recognition ? "重新识别" : "识别题目文字"}
                </button>
              </div>
            )}
          </div>

          {isImage && providers.isSuccess && visionProviders.length === 0 && (
            <div className="form-message is-warning">未配置视觉模型，无法自动读取图片。你仍可以手动输入题目文字，或先前往设置页面配置。</div>
          )}
          {risky && (
            <div className="form-message is-warning">
              <strong>题目识别可能不完整，请检查或手动修改后再分析。</strong>
              {recognition.missing_information.length > 0 && <span>缺失提示：{recognition.missing_information.join("；")}</span>}
            </div>
          )}
          {recognition?.warnings.map((warning) => <div className="recognition-warning" key={warning}>注意：{warning}</div>)}

          <label>识别出的题目文字
            <textarea required value={confirmedText} onChange={(event) => {
              setConfirmedText(event.target.value);
              setAcknowledged(false);
              setSaved(false);
            }} placeholder={isImage ? "识别后将在这里显示；也可以手动输入完整题目" : "请核对题目文字"} />
          </label>

          {recognition && (
            <div className="recognition-meta">
              <span>识别可信度：<strong>{CONFIDENCE_LABELS[recognition.confidence]}</strong></span>
              <span>模型：{recognition.model_name}</span>
              <span>提示词版本：{recognition.prompt_version}</span>
            </div>
          )}

          <div className="form-grid two-columns">
            <label>所属学科（可选）<input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="例如：初中数学" /></label>
            <label>年级（可选）<input value={grade} onChange={(event) => setGrade(event.target.value)} placeholder="例如：八年级" /></label>
          </div>
          <details className="student-context">
            <summary>补充我的答案或解题过程（可选）</summary>
            <label>我的答案<input value={userAnswer} onChange={(event) => setUserAnswer(event.target.value)} /></label>
            <label>我的解题过程<textarea value={userSolution} onChange={(event) => setUserSolution(event.target.value)} /></label>
          </details>

          <label className="confirmation-check">
            <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
            <span><strong>我已确认题目文字和条件完整</strong><small>修改题目文字后需要重新确认</small></span>
          </label>
          {error && <div className="form-message is-error" role="alert">{error}</div>}
          {saved && (
            <div className="confirmation-success">
              <div className="form-message is-success" role="status"><strong>题目已确认</strong>，后续分析只会使用这份确认文本。</div>
              <Link className="primary-action start-analysis-link" to={`/questions/${id}/analysis`}>开始分析</Link>
            </div>
          )}
          <button className="primary-action confirm-action" type="submit" disabled={saving || !confirmedText.trim() || !acknowledged}>
            {saving ? "正在确认…" : "确认题目"}
          </button>
        </form>
      </div>
    </main>
  );
}
