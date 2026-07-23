import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";

import { HealthStatus } from "./components/HealthStatus";
import { HomePage } from "./pages/HomePage";

const AnalysisPage = lazy(() =>
  import("./pages/AnalysisPage").then((module) => ({ default: module.AnalysisPage })),
);
const ConfirmQuestionPage = lazy(() =>
  import("./pages/ConfirmQuestionPage").then((module) => ({ default: module.ConfirmQuestionPage })),
);
const NotebookPage = lazy(() =>
  import("./pages/NotebookPage").then((module) => ({ default: module.NotebookPage })),
);
const ReviewPage = lazy(() =>
  import("./pages/ReviewPage").then((module) => ({ default: module.ReviewPage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })),
);

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
});

function Layout() {
  const [dark, setDark] = useState(false);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
  }

  return (
    <div className="app-frame">
      <header className="topbar">
        <Link className="brand" to="/" aria-label="AI 错题复盘工作台首页">
          <span className="brand-mark" aria-hidden="true">错</span>
          <span><strong>AI 错题复盘</strong><small>本地学习工作台</small></span>
        </Link>
        <nav aria-label="主导航">
          <NavLink to="/">首页</NavLink>
          <NavLink to="/notebook">错题本</NavLink>
          <NavLink to="/review">复习中心</NavLink>
          <NavLink to="/settings">设置</NavLink>
        </nav>
        <div className="topbar-tools">
          <HealthStatus />
          <button className="theme-button" onClick={toggleTheme} type="button" aria-label="切换深色模式">
            {dark ? "☀" : "◐"}
          </button>
        </div>
      </header>
      <Suspense fallback={<main className="page-shell"><div className="empty-state">正在打开页面…</div></main>}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/questions/:id/confirm" element={<ConfirmQuestionPage />} />
          <Route path="/questions/:id/analysis" element={<AnalysisPage />} />
          <Route path="/notebook" element={<NotebookPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Suspense>
      <footer>AI 内容可能存在错误，请结合教材或老师讲解核对。</footer>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
