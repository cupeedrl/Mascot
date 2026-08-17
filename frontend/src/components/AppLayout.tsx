import { useEffect, useState, type ComponentType } from "react";
import {
  BookOpen,
  Dumbbell,
  LayoutDashboard,
  Library,
  LogOut,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

interface NavigationItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  end?: boolean;
}

const navigation: NavigationItem[] = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/learn", label: "Learn", icon: BookOpen },
  { to: "/app/vocabulary", label: "My Vocabulary", icon: Library },
  { to: "/app/review", label: "Review", icon: RefreshCw },
  { to: "/app/practice", label: "Practice", icon: Dumbbell },
];

function NavigationLinks({ mobile = false }: { mobile?: boolean }) {
  return navigation.map(({ to, label, icon: Icon, end }) => (
    <NavLink key={to} to={to} end={end} aria-label={label}>
      <Icon size={mobile ? 21 : 19} strokeWidth={2} aria-hidden="true" />
      <span>{label}</span>
    </NavLink>
  ));
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.pathname]);

  async function handleLogout() {
    setIsLoggingOut(true);
    await logout();
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <NavLink className="wordmark" to="/app" aria-label="Mascot Dashboard">
          <span className="wordmark-symbol" aria-hidden="true">
            <Sparkles size={20} strokeWidth={2.2} />
          </span>
          <span>Mascot</span>
        </NavLink>

        <div className="sidebar-context">
          <span>Current journey</span>
          <strong>General English</strong>
          <small>Build your vocabulary daily</small>
        </div>

        <nav className="app-navigation" aria-label="Điều hướng chính">
          <NavigationLinks />
        </nav>

        <div className="account-summary">
          <div className="account-avatar" aria-hidden="true">
            {user?.email?.charAt(0).toUpperCase() ?? "M"}
          </div>
          <div className="account-copy">
            <strong>Learner</strong>
            <span title={user?.email}>{user?.email}</span>
          </div>
          <button
            className="icon-button logout-button"
            type="button"
            aria-label="Đăng xuất"
            title="Đăng xuất"
            onClick={handleLogout}
            disabled={isLoggingOut}
          >
            <LogOut size={18} aria-hidden="true" />
          </button>
        </div>
      </aside>

      <header className="mobile-topbar">
        <NavLink className="wordmark" to="/app">
          <span className="wordmark-symbol" aria-hidden="true">
            <Sparkles size={18} />
          </span>
          <span>Mascot</span>
        </NavLink>
        <button
          className="icon-button"
          type="button"
          aria-label="Đăng xuất"
          onClick={handleLogout}
          disabled={isLoggingOut}
        >
          <LogOut size={19} aria-hidden="true" />
        </button>
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <nav className="mobile-navigation" aria-label="Điều hướng chính trên di động">
        <NavigationLinks mobile />
      </nav>
    </div>
  );
}
