import { type ReactNode } from "react";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { PageSkeleton } from "./PageSkeleton";

export function AdminRoute({ children }: { children: ReactNode }) {
  const { user, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <PageSkeleton />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (user.role !== "admin") {
    return (
      <main className="auth-layout" style={{ gridTemplateColumns: "1fr" }}>
        <section className="form-panel" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
          <div className="auth-card" style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
            <div className="auth-invalid-icon" style={{ width: "60px", height: "60px", background: "rgba(220, 38, 38, 0.1)", color: "#dc2626" }}>
              <ShieldAlert size={32} />
            </div>
            <h2>Quyền truy cập bị từ chối</h2>
            <p style={{ color: "var(--muted)", margin: 0 }}>
              Khu vực quản trị chỉ dành cho tài khoản có quyền Quản trị viên (Admin).
            </p>
            <Link className="primary-button" to="/app" style={{ width: "100%", marginTop: "8px" }}>
              <ArrowLeft size={16} /> Quay lại trang học tập
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}
