import { Link, useLocation } from "react-router-dom";
import { t } from "../lib/i18n";

export default function Header() {
  const location = useLocation();

  const navItems = [
    { path: "/", label: t('nav.capture') },
    { path: "/history", label: t('nav.history') },
    { path: "/settings", label: t('nav.settings') },
  ];

  return (
    <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-2">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          FormulaSnap
        </h1>
      </div>
      <nav className="flex space-x-4">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`px-3 py-2 rounded-md text-sm font-medium ${
              location.pathname === item.path
                ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200"
                : "text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
