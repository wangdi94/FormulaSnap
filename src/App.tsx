import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { listen } from "@tauri-apps/api/event";
import Header from "./components/Header";
import StatusBar from "./components/StatusBar";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toast";
import { Spinner } from "./components/Spinner";
import { applyTheme, getTheme } from "./lib/theme";
import { initSidecarPort } from "./lib/sidecarClient";
import "./App.css";

const HomePage = lazy(() => import("./pages/HomePage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const HistoryDetailPage = lazy(() => import("./pages/HistoryDetailPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const SelectionPage = lazy(() => import("./pages/SelectionPage"));

function NavigationListener() {
  const navigate = useNavigate();

  useEffect(() => {
    const unlisten = listen<string>("navigate", (event) => {
      navigate(event.payload);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [navigate]);

  return null;
}

function MainLayout() {
  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      <Header />
      <main className="flex-1 overflow-auto">
        <Suspense fallback={<div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/history/:id" element={<HistoryDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Suspense>
      </main>
      <StatusBar />
    </div>
  );
}

function App() {
  const location = useLocation();

  useEffect(() => {
    void initSidecarPort();
    applyTheme(getTheme());

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (getTheme() === "system") applyTheme("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  if (location.pathname === "/selection") {
    return (
      <>
        <NavigationListener />
        <ErrorBoundary>
          <Suspense fallback={<div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>}>
            <SelectionPage />
          </Suspense>
        </ErrorBoundary>
      </>
    );
  }

  return (
    <>
      <NavigationListener />
      <ErrorBoundary>
        <MainLayout />
      </ErrorBoundary>
    </>
  );
}

function AppWithRouter() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <App />
      </ToastProvider>
    </BrowserRouter>
  );
}

export default AppWithRouter;
