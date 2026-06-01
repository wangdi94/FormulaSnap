import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { listen } from "@tauri-apps/api/event";
import Header from "./components/Header";
import StatusBar from "./components/StatusBar";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toast";
import HomePage from "./pages/HomePage";
import HistoryPage from "./pages/HistoryPage";
import HistoryDetailPage from "./pages/HistoryDetailPage";
import SettingsPage from "./pages/SettingsPage";
import SelectionPage from "./pages/SelectionPage";
import { applyTheme, getTheme } from "./lib/theme";
import { initSidecarPort } from "./lib/sidecarClient";
import "./App.css";

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
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:id" element={<HistoryDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
      <StatusBar />
    </div>
  );
}

function App() {
  const location = useLocation();

  useEffect(() => {
    initSidecarPort();
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
        <SelectionPage />
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
