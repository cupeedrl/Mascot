import { useEffect, useState, type ComponentType } from "react";
import {
  BookOpen,
  Dumbbell,
  Info,
  LayoutDashboard,
  Library,
  LogOut,
  RefreshCw,
  Shield,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { PenguinMark } from "./PenguinMark";

interface NavigationItem {
  to: string;
  label: string;
  shortLabel?: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  end?: boolean;
}

const navigation: NavigationItem[] = [
  { to: "/app", label: "Trang chủ", icon: LayoutDashboard, end: true },
  { to: "/app/learn", label: "Học từ vựng", shortLabel: "Học từ", icon: BookOpen },
  { to: "/app/vocabulary", label: "Từ vựng của tôi", shortLabel: "Từ của tôi", icon: Library },
  { to: "/app/review", label: "Ôn tập", icon: RefreshCw },
  { to: "/app/practice", label: "Luyện tập", icon: Dumbbell },
  { to: "/app/about", label: "Giới thiệu", icon: Info },
];

function NavigationLinks({ mobile = false }: { mobile?: boolean }) {
  return navigation.map(({ to, label, shortLabel, icon: Icon, end }) => (
    <NavLink key={to} to={to} end={end} aria-label={label}>
      <Icon size={mobile ? 20 : 19} strokeWidth={2} aria-hidden="true" />
      <span>{mobile ? (shortLabel ?? label) : label}</span>
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
        <NavLink className="wordmark" to="/app" aria-label="Trang chủ Mascot">
          <PenguinMark size={38} />
          <span>Mascot</span>
        </NavLink>

        <div className="sidebar-context">
          <span>Hành trình hiện tại</span>
          <strong>Tiếng Anh tổng quát</strong>
          <small>Xây dựng vốn từ mỗi ngày</small>
        </div>

        <nav className="app-navigation" aria-label="Điều hướng chính">
          <NavigationLinks />
        </nav>

        {user?.role === "admin" && (
          <NavLink className="admin-portal-link" to="/admin" aria-label="Khu vực quản trị">
            <Shield size={15} />
            <span>Trang quản trị</span>
          </NavLink>
        )}

        <div className="account-summary">
          <div className="account-avatar" aria-hidden="true">
            {user?.email?.charAt(0).toUpperCase() ?? "M"}
          </div>
          <div className="account-copy">
            <strong>Mascoter</strong>
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
          <PenguinMark size={34} />
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
