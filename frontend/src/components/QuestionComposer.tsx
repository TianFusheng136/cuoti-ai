import { useQuery } from "@tanstack/react-query";
import { ChangeEvent, DragEvent, FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listProviders } from "../api/providers";
import { createImageQuestion, createTextQuestion } from "../api/questions";

const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
const SUPPORTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

type ImageSource = "image" | "clipboard";

type SelectedImage = {
  file: File;
  source: ImageSource;
};

function validateImage(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const supportedExtension = SUPPORTED_EXTENSIONS.some((item) => lowerName.endsWith(item));
  if (!supportedExtension || (file.type && !SUPPORTED_TYPES.has(file.type))) {
    return "仅支持 JPG、PNG 或 WebP 格式的题目图片。";
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return "图片不能超过 15MB，请压缩或裁切后重试。";
  }
  return null;
}

export function QuestionComposer() {
  const navigate = useNavigate();
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const visionReady = providers.data?.some(
    (provider) => provider.capability === "vision" && provider.enabled,
  );
  const textReady = providers.data?.some(
    (provider) => provider.capability === "text" && provider.enabled,
  );
  const fileInput = useRef<HTMLInputElement>(null);
  const [showTextForm, setShowTextForm] = useState(false);
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<SelectedImage | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(selected.file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selected]);

  function chooseImage(file: File, source: ImageSource) {
    const validationError = validateImage(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setMessage(null);
    setShowTextForm(false);
    setSelected({ file, source });
  }

  useEffect(() => {
    function handlePaste(event: ClipboardEvent) {
      const imageItem = [...(event.clipboardData?.items ?? [])].find(
        (item) => item.kind === "file" && item.type.startsWith("image/"),
      );
      const pasted = imageItem?.getAsFile();
      if (!pasted) return;
      event.preventDefault();
      const extension = pasted.type === "image/jpeg" ? ".jpg" : `.${pasted.type.split("/")[1]}`;
      const file = new File([pasted], pasted.name || `剪贴板题目${extension}`, {
        type: pasted.type,
      });
      chooseImage(file, "clipboard");
    }
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  });

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) chooseImage(file, "image");
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) chooseImage(file, "image");
  }

  async function submitText(event: FormEvent) {
    event.preventDefault();
    const normalized = text.trim();
    if (!normalized) {
      setError("请输入完整的题目文字。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const draft = await createTextQuestion(normalized);
      setMessage("文字题目已保存");
      navigate(`/questions/${draft.id}/confirm`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "文字题目保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function submitImage() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const draft = await createImageQuestion(selected.file, selected.source);
      setMessage("题目图片已保存");
      navigate(`/questions/${draft.id}/confirm`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "图片保存失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="composer"
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      <input
        ref={fileInput}
        className="visually-hidden"
        aria-label="选择题目图片"
        type="file"
        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
      />
      <div className="entry-grid">
        <button
          className="entry-card entry-primary"
          type="button"
          aria-label="上传题目图片"
          onClick={() => fileInput.current?.click()}
        >
          <span className="entry-icon" aria-hidden="true">＋</span>
          <span><strong>上传题目图片</strong><small>拖拽、选择或粘贴截图</small></span>
        </button>
        <button
          className="entry-card"
          type="button"
          aria-label="直接输入题目"
          onClick={() => {
            setShowTextForm(true);
            setSelected(null);
            setMessage(null);
            setError(null);
          }}
        >
          <span className="entry-icon text-icon" aria-hidden="true">文</span>
          <span><strong>直接输入题目</strong><small>没有图片也可以开始复盘</small></span>
        </button>
      </div>

      {providers.isSuccess && (!visionReady || !textReady) && (
        <div className="model-readiness" aria-label="模型配置状态">
          {!visionReady && <span>未配置视觉模型：图片可保存在本机，但暂不能识别</span>}
          {!textReady && <span>未配置文本模型：题目可以录入，但暂不能分析</span>}
        </div>
      )}

      {showTextForm && (
        <form className="composer-panel text-composer" onSubmit={submitText}>
          <div className="composer-heading">
            <div><strong>输入题目文字</strong><small>请尽量包含所有条件、选项和单位</small></div>
            <button type="button" className="close-button" onClick={() => setShowTextForm(false)} aria-label="关闭">×</button>
          </div>
          <label htmlFor="question-text">题目文字</label>
          <textarea
            id="question-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="例如：解方程 x² - 5x + 6 = 0"
            maxLength={50000}
            autoFocus
          />
          <div className="composer-actions">
            <span>{text.length.toLocaleString()} / 50,000</span>
            <button className="primary-action" type="submit" disabled={busy}>
              {busy ? "正在保存…" : "保存文字题目"}
            </button>
          </div>
        </form>
      )}

      {selected && previewUrl && (
        <div className="composer-panel image-preview-panel">
          <img src={previewUrl} alt="待上传的题目预览" />
          <div className="preview-details">
            <strong>{selected.file.name}</strong>
            <span>{(selected.file.size / 1024).toFixed(1)} KB · 保存前请检查图片是否清晰完整</span>
            <div className="preview-actions">
              <button type="button" className="secondary-action" onClick={() => setSelected(null)}>重新选择</button>
              <button type="button" className="primary-action" onClick={submitImage} disabled={busy || message === "题目图片已保存"}>
                {busy ? "正在保存…" : "保存题目图片"}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && <div className="form-message is-error" role="alert">{error}</div>}
      {message && <div className="form-message is-success" role="status"><strong>{message}</strong>，下一步将在确认页检查题目信息。</div>}
    </div>
  );
}
