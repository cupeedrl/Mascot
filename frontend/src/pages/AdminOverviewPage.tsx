import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  ClipboardCheck,
  Library,
  RefreshCw,
  Users,
} from "lucide-react";

import { AdminOverviewResponse, ApiError, getAdminOverview } from "../api/client";

export function AdminOverviewPage() {
  const [data, setData] = useState<AdminOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminOverview();
      setData(res);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể tải thông tin quản trị hệ thống.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="admin-page-container">
      <header className="admin-page-header">
        <div>
          <p className="admin-eyebrow">QUẢN TRỊ MASCOT</p>
          <h1>Tổng quan hệ thống</h1>
          <p className="admin-subtext">
            Thông tin nhanh về người dùng, nội dung và hoạt động của Mascot.
          </p>
        </div>
        <button
          className="secondary-button admin-refresh-btn"
          type="button"
          onClick={fetchData}
          disabled={isLoading}
        >
          <RefreshCw size={15} className={isLoading ? "spin" : ""} /> Làm mới
        </button>
      </header>

      {error ? (
        <div className="admin-error-box" role="alert">
          <AlertCircle size={22} />
          <div>
            <strong>Đã xảy ra lỗi</strong>
            <p>{error}</p>
          </div>
          <button className="primary-button" type="button" onClick={fetchData}>
            Thử lại
          </button>
        </div>
      ) : isLoading || !data ? (
        <div className="admin-metrics-grid" aria-label="Đang tải dữ liệu...">
          {[1, 2, 3, 4].map((index) => (
            <div key={index} className="admin-metric-card admin-metric-skeleton">
              <div className="skeleton-line" style={{ width: "40px", height: "40px", borderRadius: "12px" }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton-line" style={{ width: "60%", height: "12px", marginBottom: "8px" }} />
                <div className="skeleton-line" style={{ width: "40%", height: "24px" }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="admin-metrics-grid" aria-label="Các chỉ số tổng quan">
          <article className="admin-metric-card">
            <div className="admin-metric-icon admin-icon-users">
              <Users size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Người dùng</span>
              <strong>{data.total_users.toLocaleString("vi-VN")}</strong>
              <small>Tài khoản đã đăng ký</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon admin-icon-catalog">
              <Library size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Từ trong thư viện</span>
              <strong>{data.total_catalog_entries.toLocaleString("vi-VN")}</strong>
              <small>Từ vựng danh mục chuẩn CEFR</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon admin-icon-personal">
              <BookOpen size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Từ cá nhân</span>
              <strong>{data.total_personal_vocabulary.toLocaleString("vi-VN")}</strong>
              <small>Từ trong sổ tay người học</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon admin-icon-practice">
              <ClipboardCheck size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Lượt luyện tập</span>
              <strong>{data.total_practice_sessions.toLocaleString("vi-VN")}</strong>
              <small>Bài tập đã được thực hiện</small>
            </div>
          </article>
        </div>
      )}
    </div>
  );
}
