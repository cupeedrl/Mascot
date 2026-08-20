import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  UserCheck,
  UserX,
} from "lucide-react";
import { Link } from "react-router-dom";

import {
  AdminUserListItem,
  ApiError,
  getAdminUsers,
  updateAdminUserRole,
  updateAdminUserStatus,
} from "../api/client";

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"user" | "admin" | "">("");
  const [statusFilter, setStatusFilter] = useState<"active" | "disabled" | "">("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminUsers({
        page,
        pageSize,
        search: debouncedSearch || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      });
      setUsers(res.items);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể tải danh sách người dùng.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, roleFilter, statusFilter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  async function handleToggleRole(user: AdminUserListItem) {
    const newRole = user.role === "admin" ? "user" : "admin";
    const confirmText =
      newRole === "admin"
        ? `Bạn có chắc muốn nâng cấp tài khoản ${user.email} thành Admin?`
        : `Bạn có chắc muốn hạ quyền tài khoản ${user.email} xuống User thông thường?`;

    if (!window.confirm(confirmText)) return;

    setActionLoadingId(user.id);
    setActionMessage(null);
    try {
      await updateAdminUserRole(user.id, newRole);
      setActionMessage(`Đã cập nhật quyền của ${user.email} thành ${newRole.toUpperCase()}.`);
      fetchUsers();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        alert(caughtError.message);
      } else {
        alert("Không thể cập nhật quyền người dùng.");
      }
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleToggleStatus(user: AdminUserListItem) {
    const newStatus = !user.is_active;
    const confirmText = newStatus
      ? `Bạn có chắc muốn kích hoạt lại tài khoản ${user.email}?`
      : `Bạn có chắc muốn vô hiệu hóa tài khoản ${user.email}? Người dùng sẽ không thể đăng nhập hoặc thao tác.`;

    if (!window.confirm(confirmText)) return;

    setActionLoadingId(user.id);
    setActionMessage(null);
    try {
      await updateAdminUserStatus(user.id, newStatus);
      setActionMessage(
        `Đã ${newStatus ? "kích hoạt" : "vô hiệu hóa"} tài khoản ${user.email}.`,
      );
      fetchUsers();
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        alert(caughtError.message);
      } else {
        alert("Không thể cập nhật trạng thái người dùng.");
      }
    } finally {
      setActionLoadingId(null);
    }
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  return (
    <div className="admin-page-container">
      <header className="admin-page-header">
        <div>
          <p className="admin-eyebrow">QUẢN TRỊ NGƯỜI DÙNG</p>
          <h1>Danh sách người dùng</h1>
          <p className="admin-subtext">
            Quản lý tài khoản, phân quyền và theo dõi hoạt động ({total} người dùng).
          </p>
        </div>
        <button
          className="secondary-button admin-refresh-btn"
          type="button"
          onClick={fetchUsers}
          disabled={isLoading}
        >
          <RefreshCw size={15} className={isLoading ? "spin" : ""} /> Làm mới
        </button>
      </header>

      {actionMessage && (
        <div className="admin-success-box">
          <CheckCircle2 size={18} />
          <span>{actionMessage}</span>
        </div>
      )}

      {error && (
        <div className="admin-error-box" role="alert">
          <AlertCircle size={20} />
          <div>
            <strong>Lỗi tải dữ liệu</strong>
            <p>{error}</p>
          </div>
          <button className="primary-button" type="button" onClick={fetchUsers}>
            Thử lại
          </button>
        </div>
      )}

      <div className="admin-filter-bar">
        <div className="admin-search-input">
          <Search size={16} />
          <input
            type="search"
            placeholder="Tìm theo email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="admin-select-group">
          <label htmlFor="role-select">Vai trò:</label>
          <select
            id="role-select"
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value as "user" | "admin" | "");
              setPage(1);
            }}
          >
            <option value="">Tất cả vai trò</option>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        <div className="admin-select-group">
          <label htmlFor="status-select">Trạng thái:</label>
          <select
            id="status-select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as "active" | "disabled" | "");
              setPage(1);
            }}
          >
            <option value="">Tất cả trạng thái</option>
            <option value="active">Hoạt động</option>
            <option value="disabled">Vô hiệu hóa</option>
          </select>
        </div>
      </div>

      <div className="admin-table-container">
        <table className="admin-table" aria-label="Bảng danh sách người dùng">
          <thead>
            <tr>
              <th>Email</th>
              <th>Vai trò</th>
              <th>Trạng thái</th>
              <th>Ngày đăng ký</th>
              <th>Hoạt động gần nhất</th>
              <th style={{ textAlign: "right" }}>Từ cá nhân</th>
              <th style={{ textAlign: "right" }}>Bài luyện</th>
              <th style={{ textAlign: "center" }}>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "40px" }}>
                  <RefreshCw size={24} className="spin" style={{ margin: "0 auto 8px" }} />
                  <p style={{ color: "var(--muted)", margin: 0 }}>Đang tải người dùng...</p>
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "48px" }}>
                  <p style={{ color: "var(--muted)", fontSize: "14px", margin: 0 }}>
                    Không tìm thấy người dùng nào phù hợp với bộ lọc.
                  </p>
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <Link
                      to={`/admin/users/${u.id}`}
                      className="admin-table-link"
                      title="Xem chi tiết người dùng"
                    >
                      {u.email}
                    </Link>
                  </td>
                  <td>
                    <span
                      className={`admin-role-badge ${
                        u.role === "admin" ? "badge-admin" : "badge-user"
                      }`}
                    >
                      {u.role === "admin" ? <Shield size={11} /> : null}
                      {u.role === "admin" ? "Admin" : "User"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`admin-status-badge ${
                        u.is_active ? "status-active" : "status-disabled"
                      }`}
                    >
                      {u.is_active ? "Hoạt động" : "Vô hiệu hóa"}
                    </span>
                  </td>
                  <td>{formatDate(u.created_at)}</td>
                  <td>{formatDate(u.last_active_at)}</td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>
                    {u.personal_vocabulary_count.toLocaleString("vi-VN")}
                  </td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>
                    {u.practice_session_count.toLocaleString("vi-VN")}
                  </td>
                  <td>
                    <div className="admin-actions-cell">
                      <button
                        className="admin-mini-btn"
                        type="button"
                        onClick={() => handleToggleRole(u)}
                        disabled={actionLoadingId === u.id}
                        title={
                          u.role === "admin"
                            ? "Hạ quyền thành User"
                            : "Nâng cấp thành Admin"
                        }
                      >
                        {u.role === "admin" ? "Hạ quyền" : "Cấp Admin"}
                      </button>

                      <button
                        className={`admin-mini-btn ${
                          u.is_active ? "btn-danger" : "btn-success"
                        }`}
                        type="button"
                        onClick={() => handleToggleStatus(u)}
                        disabled={actionLoadingId === u.id}
                        title={
                          u.is_active ? "Vô hiệu hóa tài khoản" : "Kích hoạt lại"
                        }
                      >
                        {u.is_active ? (
                          <UserX size={13} />
                        ) : (
                          <UserCheck size={13} />
                        )}
                        {u.is_active ? "Khóa" : "Mở"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <footer className="admin-pagination">
          <span>
            Trang <strong>{page}</strong> / {totalPages} (Tổng {total} người dùng)
          </span>
          <div className="admin-pagination-btns">
            <button
              className="secondary-button"
              type="button"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft size={16} /> Trước
            </button>
            <button
              className="secondary-button"
              type="button"
              disabled={page >= totalPages || isLoading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Sau <ChevronRight size={16} />
            </button>
          </div>
        </footer>
      )}
    </div>
  );
}
