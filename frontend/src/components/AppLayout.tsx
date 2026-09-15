import { useEffect, useRef, useState, type ComponentType } from "react";
import {
  BookOpen,
  ChevronDown,
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
import { useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";
import { AIChatDrawer } from "./AIChatDrawer";
import { BeeMark } from "./BeeMark";

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
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const { activeTrack } = useActiveLearningTrack();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.pathname]);

  useEffect(() => {
    if (!isAccountMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) setIsAccountMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsAccountMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isAccountMenuOpen]);

  async function handleLogout() {
    setIsAccountMenuOpen(false);
    setIsLoggingOut(true);
    await logout();
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <NavLink className="wordmark" to="/app" aria-label="Trang chủ Mascot">
          <BeeMark size={38} />
          <span>Mascot</span>
        </NavLink>

        <div className="sidebar-context">
          <span>Hành trình hiện tại</span>
          <strong>{activeTrack?.name ?? "Đang tải lộ trình…"}</strong>
          <small>{activeTrack ? `${activeTrack.language.name} · ${activeTrack.level_framework}` : "Xây dựng vốn từ mỗi ngày"}</small>
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

      </aside>

      <header className="desktop-account-bar" aria-label="Tài khoản người dùng">
        <div className="desktop-account-menu" ref={accountMenuRef}>
          <button
            className="desktop-account-trigger"
            type="button"
            aria-haspopup="menu"
            aria-expanded={isAccountMenuOpen}
            onClick={() => setIsAccountMenuOpen((isOpen) => !isOpen)}
          >
            <span className="account-avatar" aria-hidden="true">
              {user?.email?.charAt(0).toUpperCase() ?? "M"}
            </span>
            <span className="desktop-account-copy">
              <strong>Mascoter</strong>
              <small>{user?.email}</small>
            </span>
            <ChevronDown size={16} aria-hidden="true" />
          </button>
          {isAccountMenuOpen && (
            <div className="desktop-account-dropdown" role="menu">
              <div>
                <strong>Mascoter</strong>
                <span title={user?.email}>{user?.email}</span>
              </div>
              <button type="button" role="menuitem" onClick={handleLogout} disabled={isLoggingOut}>
                <LogOut size={16} aria-hidden="true" />
                {isLoggingOut ? "Đang đăng xuất…" : "Đăng xuất"}
              </button>
            </div>
          )}
        </div>
      </header>

      <header className="mobile-topbar">
        <NavLink className="wordmark" to="/app">
          <BeeMark size={34} />
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

      <AIChatDrawer />
    </div>
  );
}

