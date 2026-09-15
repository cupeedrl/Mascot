import { useState } from "react";
import {
  ArrowLeft,
  BrainCircuit,
  LayoutDashboard,
  Library,
  LogOut,
  Shield,
  Users,
} from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { BeeMark } from "./BeeMark";

export function AdminLayout() {
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function handleLogout() {
    setIsLoggingOut(true);
    await logout();
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar" aria-label="Bảng điều khiển quản trị">
        <div className="admin-wordmark">
          <BeeMark size={34} />
          <div className="admin-brand-copy">
            <strong>Mascot</strong>
            <span className="admin-badge"><Shield size={11} /> Admin</span>
          </div>
        </div>

        <nav className="admin-navigation" aria-label="Điều hướng quản trị">
          <p className="admin-nav-section">HỆ THỐNG</p>
          <NavLink to="/admin" end className={({ isActive }) => (isActive ? "active" : "")}>
            <LayoutDashboard size={18} />
            <span>Tổng quan</span>
          </NavLink>

          <p className="admin-nav-section">QUẢN LÝ</p>
          <NavLink to="/admin/users" className={({ isActive }) => (isActive ? "active" : "")}>
            <Users size={18} />
            <span>Người dùng</span>
          </NavLink>

          <NavLink to="/admin/catalog" className={({ isActive }) => (isActive ? "active" : "")}>
            <Library size={18} />
            <span>Thư viện từ</span>
          </NavLink>

          <p className="admin-nav-section">THEO DÕI</p>
          <NavLink to="/admin/ai-usage" className={({ isActive }) => (isActive ? "active" : "")}>
            <BrainCircuit size={18} />
            <span>AI Usage</span>
          </NavLink>
        </nav>

        <div className="admin-sidebar-footer">
          <Link to="/app" className="admin-back-learner">
            <ArrowLeft size={16} /> Quay lại Mascot
          </Link>

          <div className="admin-account-card">
            <div className="admin-avatar" aria-hidden="true">
              {user?.email?.charAt(0).toUpperCase() ?? "A"}
            </div>
            <div className="admin-account-copy">
              <strong>Quản trị viên</strong>
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
              <LogOut size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
