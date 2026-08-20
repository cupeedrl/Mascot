import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Dumbbell,
  Flame,
  RefreshCw,
  Shield,
  Target,
  UserCheck,
  UserX,
  XCircle,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import {
  AdminUserDetailResponse,
  ApiError,
  getAdminUserDetail,
  updateAdminUserRole,
  updateAdminUserStatus,
} from "../api/client";

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const [user, setUser] = useState<AdminUserDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const fetchUser = useCallback(async () => {
    if (!userId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminUserDetail(userId);
      setUser(res);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể tải thông tin chi tiết người dùng.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  async function handleToggleRole() {
    if (!user) return;
    const newRole = user.role === "admin" ? "user" : "admin";
    const confirmText =
      newRole === "admin"
        ? `Nâng cấp tài khoản ${user.email} thành Admin?`
        : `Hạ quyền tài khoản ${user.email} xuống User?`;

    if (!window.confirm(confirmText)) return;

    setIsActionLoading(true);
    setActionMessage(null);
    try {
      await updateAdminUserRole(user.id, newRole);
      setActionMessage(`Đã cập nhật quyền thành công sang ${newRole.toUpperCase()}.`);
      fetchUser();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        alert(caughtError.message);
      } else {
        alert("Không thể cập nhật quyền người dùng.");
      }
    } finally {
      setIsActionLoading(false);
    }
  }

  async function handleToggleStatus() {
    if (!user) return;
    const newStatus = !user.is_active;
    const confirmText = newStatus
      ? `Kích hoạt lại tài khoản ${user.email}?`
      : `Vô hiệu hóa tài khoản ${user.email}?`;

    if (!window.confirm(confirmText)) return;

    setIsActionLoading(true);
    setActionMessage(null);
    try {
      await updateAdminUserStatus(user.id, newStatus);
      setActionMessage(
        `Đã ${newStatus ? "kích hoạt lại" : "vô hiệu hóa"} tài khoản thành công.`,
      );
      fetchUser();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        alert(caughtError.message);
      } else {
        alert("Không thể cập nhật trạng thái người dùng.");
      }
    } finally {
      setIsActionLoading(false);
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (isLoading && !user) {
    return (
      <div className="admin-page-container">
        <Link to="/admin/users" className="admin-back-learner">
          <ArrowLeft size={16} /> Quay lại danh sách
        </Link>
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <RefreshCw size={28} className="spin" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--muted)" }}>Đang tải thông tin người dùng...</p>
        </div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="admin-page-container">
        <Link to="/admin/users" className="admin-back-learner">
          <ArrowLeft size={16} /> Quay lại danh sách
        </Link>
        <div className="admin-error-box" role="alert">
          <AlertCircle size={22} />
          <div>
            <strong>Lỗi tải thông tin</strong>
            <p>{error ?? "Người dùng không tồn tại."}</p>
          </div>
          <button className="primary-button" type="button" onClick={fetchUser}>
            Thử lại
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page-container">
      <Link to="/admin/users" className="admin-back-learner">
        <ArrowLeft size={16} /> Quay lại danh sách người dùng
      </Link>

      {actionMessage && (
        <div className="admin-success-box">
          <CheckCircle2 size={18} />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* User Header Profile Card */}
      <section className="admin-user-header-card">
        <div className="admin-user-avatar-large">
          {user.email.charAt(0).toUpperCase()}
        </div>
        <div className="admin-user-header-info">
          <div className="admin-user-title-row">
            <h2>{user.email}</h2>
            <span
              className={`admin-role-badge ${
                user.role === "admin" ? "badge-admin" : "badge-user"
              }`}
            >
              {user.role === "admin" ? <Shield size={12} /> : null}
              {user.role === "admin" ? "Quản trị viên" : "Người học"}
            </span>
            <span
              className={`admin-status-badge ${
                user.is_active ? "status-active" : "status-disabled"
              }`}
            >
              {user.is_active ? "Hoạt động" : "Vô hiệu hóa"}
            </span>
          </div>

          <div className="admin-user-meta-row">
            <span>ID: <code>{user.id}</code></span>
            <span>Ngày đăng ký: <strong>{formatDate(user.created_at)}</strong></span>
            <span>Hoạt động gần nhất: <strong>{formatDate(user.last_active_at)}</strong></span>
          </div>
        </div>

        <div className="admin-user-header-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={handleToggleRole}
            disabled={isActionLoading}
          >
            <Shield size={15} />
            {user.role === "admin" ? "Hạ quyền User" : "Cấp quyền Admin"}
          </button>

          <button
            className={`secondary-button ${user.is_active ? "btn-danger" : "btn-success"}`}
            type="button"
            onClick={handleToggleStatus}
            disabled={isActionLoading}
          >
            {user.is_active ? <UserX size={15} /> : <UserCheck size={15} />}
            {user.is_active ? "Vô hiệu hóa" : "Kích hoạt lại"}
          </button>
        </div>
      </section>

      {/* Metrics Grid */}
      <section className="admin-metrics-grid">
        <article className="admin-metric-card">
          <div className="admin-metric-icon admin-icon-personal">
            <BookOpen size={22} />
          </div>
          <div className="admin-metric-info">
            <span>Tổng từ vựng</span>
            <strong>{user.total_vocabulary.toLocaleString("vi-VN")}</strong>
            <small>Đang học: {user.learning_words} · Thành thạo: {user.mastered_words}</small>
          </div>
        </article>

        <article className="admin-metric-card">
          <div className="admin-metric-icon admin-icon-practice">
            <Dumbbell size={22} />
          </div>
          <div className="admin-metric-info">
            <span>Lượt luyện tập</span>
            <strong>{user.exercises_completed.toLocaleString("vi-VN")}</strong>
            <small>Độ chính xác: {user.exercise_accuracy}%</small>
          </div>
        </article>

        <article className="admin-metric-card">
          <div className="admin-metric-icon" style={{ background: "#fff7ed", color: "#ea580c" }}>
            <Flame size={22} />
          </div>
          <div className="admin-metric-info">
            <span>Chuỗi ngày học</span>
            <strong>{user.current_streak} ngày</strong>
            <small>Kỷ lục: {user.longest_streak} ngày liên tiếp</small>
          </div>
        </article>
      </section>

      {/* Recent Activity Table */}
      <section className="admin-section-block">
        <div className="admin-section-title">
          <h3>Lịch sử luyện tập gần đây</h3>
          <span className="admin-subtext">10 lượt làm bài tập gần nhất của người dùng</span>
        </div>

        {user.recent_activity.length === 0 ? (
          <div className="admin-empty-card">
            <p>Chưa có lượt làm bài tập nào được ghi nhận.</p>
          </div>
        ) : (
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>Kết quả</th>
                  <th>Câu trả lời của người học</th>
                  <th>Đáp án chính xác</th>
                </tr>
              </thead>
              <tbody>
                {user.recent_activity.map((act) => (
                  <tr key={act.id}>
                    <td>{formatDate(act.completed_at)}</td>
                    <td>
                      <span
                        className={`admin-result-badge ${
                          act.is_correct ? "result-correct" : "result-incorrect"
                        }`}
                      >
                        {act.is_correct ? (
                          <CheckCircle2 size={13} />
                        ) : (
                          <XCircle size={13} />
                        )}
                        {act.is_correct ? "Đúng" : "Sai"}
                      </span>
                    </td>
                    <td><code>{act.user_answer}</code></td>
                    <td><code>{act.correct_answer}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
