import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { warmupStatusMessage } from "../api/backendWarmup";
import { useAuth } from "./AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const {
    user,
    isInitializing,
    restoreUnavailable,
    restoreStatus,
    retryRestore,
  } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return (
      <div className="page-message">
        {restoreStatus
          ? warmupStatusMessage(restoreStatus)
          : "Đang kiểm tra phiên đăng nhập…"}
      </div>
    );
  }

  if (restoreUnavailable) {
    return (
      <div className="page-message">
        <section className="startup-retry-card" role="alert">
          <strong>Máy chủ mất nhiều thời gian hơn dự kiến.</strong>
          <span>Phiên đăng nhập của bạn vẫn được giữ an toàn.</span>
          <button className="primary-button" type="button" onClick={() => void retryRestore()}>
            Thử kết nối lại
          </button>
        </section>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
