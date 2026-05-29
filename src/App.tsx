import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { listen } from "@tauri-apps/api/event";
import Header from "./components/Header";
import StatusBar from "./components/StatusBar";
import HomePage from "./pages/HomePage";
import HistoryPage from "./pages/HistoryPage";
import HistoryDetailPage from "./pages/HistoryDetailPage";
import SettingsPage from "./pages/SettingsPage";
import { applyTheme, getTheme } from "./lib/theme";
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

function App() {
  useEffect(() => {
    applyTheme(getTheme());

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (getTheme() === "system") applyTheme("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <BrowserRouter>
      <NavigationListener />
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
    </BrowserRouter>
  );
}

export default App;
