import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Coins,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";

import {
  AdminAIUsageItem,
  AdminAIUsageSummary,
  ApiError,
  getAdminAIUsage,
} from "../api/client";

export function AdminAIUsagePage() {
  const [items, setItems] = useState<AdminAIUsageItem[]>([]);
  const [summary, setSummary] = useState<AdminAIUsageSummary | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [periodFilter, setPeriodFilter] = useState<"24h" | "7d" | "30d" | "all">("all");
  const [featureFilter, setFeatureFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const fetchAIUsage = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminAIUsage({
        page,
        pageSize,
        search: debouncedSearch || undefined,
        period: periodFilter !== "all" ? periodFilter : undefined,
        feature: featureFilter || undefined,
        status: statusFilter || undefined,
      });
      setItems(res.items);
      setSummary(res.summary);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể tải dữ liệu AI Usage.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, periodFilter, featureFilter, statusFilter]);

  useEffect(() => {
    fetchAIUsage();
  }, [fetchAIUsage]);

  function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function formatFeature(feat: string): string {
    if (feat === "exercise_generation") return "Tạo bài tập";
    if (feat === "vocabulary_enrichment") return "Làm giàu từ vựng";
    return feat;
  }

  return (
    <div className="admin-page-container">
      <header className="admin-page-header">
        <div>
          <p className="admin-eyebrow">QUẢN TRỊ AI</p>
          <h1>AI Usage</h1>
          <p className="admin-subtext">
            Theo dõi hoạt động sử dụng AI và các lỗi cần chú ý trong Mascot.
          </p>
        </div>
        <button
          className="secondary-button admin-refresh-btn"
          type="button"
          onClick={fetchAIUsage}
          disabled={isLoading}
        >
          <RefreshCw size={15} className={isLoading ? "spin" : ""} /> Làm mới
        </button>
      </header>

      {error && (
        <div className="admin-error-box" role="alert">
          <AlertCircle size={20} />
          <div>
            <strong>Lỗi tải dữ liệu</strong>
            <p>{error}</p>
          </div>
          <button className="primary-button" type="button" onClick={fetchAIUsage}>
            Thử lại
          </button>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <section className="admin-metrics-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <article className="admin-metric-card">
            <div className="admin-metric-icon" style={{ background: "#f3effc", color: "#7c3aed" }}>
              <BrainCircuit size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Tổng requests</span>
              <strong>{summary.total_requests.toLocaleString("vi-VN")}</strong>
              <small>Lượt gọi AI toàn hệ thống</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon" style={{ background: "#f0fdf4", color: "#16a34a" }}>
              <CheckCircle2 size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Thành công</span>
              <strong style={{ color: "#16a34a" }}>{summary.successful_requests.toLocaleString("vi-VN")}</strong>
              <small>
                {summary.total_requests > 0
                  ? `${Math.round((summary.successful_requests / summary.total_requests) * 100)}% thành công`
                  : "0%"}
              </small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon" style={{ background: "#fef2f2", color: "#dc2626" }}>
              <XCircle size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Thất bại</span>
              <strong style={{ color: "#dc2626" }}>{summary.failed_requests.toLocaleString("vi-VN")}</strong>
              <small>Lỗi provider/hệ thống</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon" style={{ background: "#fffbeb", color: "#d97706" }}>
              <AlertTriangle size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Rate Limited (429)</span>
              <strong style={{ color: "#d97706" }}>{summary.rate_limited_requests.toLocaleString("vi-VN")}</strong>
              <small>Cooldown / Quota limit</small>
            </div>
          </article>

          <article className="admin-metric-card">
            <div className="admin-metric-icon" style={{ background: "#eff6ff", color: "#2563eb" }}>
              <Clock size={22} />
            </div>
            <div className="admin-metric-info">
              <span>Độ trễ trung bình</span>
              <strong>{summary.average_latency_ms} ms</strong>
              <small>Thời gian phản hồi</small>
            </div>
          </article>

          {summary.total_tokens > 0 && (
            <article className="admin-metric-card">
              <div className="admin-metric-icon" style={{ background: "#fdf4ff", color: "#c026d3" }}>
                <Coins size={22} />
              </div>
              <div className="admin-metric-info">
                <span>Tổng Tokens</span>
                <strong>{summary.total_tokens.toLocaleString("vi-VN")}</strong>
                <small>Prompt + Completion</small>
              </div>
            </article>
          )}
        </section>
      )}

      {/* Filter Bar */}
      <div className="admin-filter-bar">
        <div className="admin-search-input">
          <Search size={16} />
          <input
            type="search"
            placeholder="Tìm theo email, model, tính năng..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="admin-select-group">
          <label htmlFor="period-select">Thời gian:</label>
          <select
            id="period-select"
            value={periodFilter}
            onChange={(e) => {
              setPeriodFilter(e.target.value as "24h" | "7d" | "30d" | "all");
              setPage(1);
            }}
          >
            <option value="all">Toàn bộ thời gian</option>
            <option value="24h">24 giờ qua</option>
            <option value="7d">7 ngày qua</option>
            <option value="30d">30 ngày qua</option>
          </select>
        </div>

        <div className="admin-select-group">
          <label htmlFor="feature-select">Tính năng:</label>
          <select
            id="feature-select"
            value={featureFilter}
            onChange={(e) => {
              setFeatureFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả tính năng</option>
            <option value="exercise_generation">Tạo bài tập</option>
            <option value="vocabulary_enrichment">Làm giàu từ vựng</option>
          </select>
        </div>

        <div className="admin-select-group">
          <label htmlFor="status-select">Trạng thái:</label>
          <select
            id="status-select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả trạng thái</option>
            <option value="success">Thành công</option>
            <option value="failed">Thất bại</option>
            <option value="rate_limited">Rate limited / 429</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="admin-table-container">
        <table className="admin-table" aria-label="Bảng nhật ký sử dụng AI">
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Người dùng</th>
              <th>Tính năng</th>
              <th>Model</th>
              <th>Trạng thái</th>
              <th style={{ textAlign: "right" }}>Độ trễ</th>
              <th style={{ textAlign: "right" }}>Tokens</th>
              <th>Chi tiết lỗi</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "40px" }}>
                  <RefreshCw size={24} className="spin" style={{ margin: "0 auto 8px" }} />
                  <p style={{ color: "var(--muted)", margin: 0 }}>Đang tải dữ liệu AI Usage...</p>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: "48px" }}>
                  <p style={{ color: "var(--muted)", fontSize: "14px", margin: 0 }}>
                    Chưa có dữ liệu sử dụng AI trong khoảng thời gian này.
                  </p>
                </td>
              </tr>
            ) : (
              items.map((log) => (
                <tr key={log.id}>
                  <td style={{ whiteSpace: "nowrap", fontSize: "12px" }}>
                    {formatDate(log.created_at)}
                  </td>
                  <td>
                    {log.user_email ? (
                      <span style={{ fontWeight: 650, color: "#1e293b" }}>{log.user_email}</span>
                    ) : (
                      <span style={{ color: "var(--muted)", fontStyle: "italic" }}>Ẩn danh</span>
                    )}
                  </td>
                  <td>
                    <span className="admin-pos-badge">{formatFeature(log.feature)}</span>
                  </td>
                  <td>
                    <code style={{ fontSize: "11px", color: "#475569" }}>{log.model}</code>
                  </td>
                  <td>
                    <span
                      className={`admin-status-badge ${
                        log.status === "success"
                          ? "status-active"
                          : log.status === "rate_limited"
                          ? "status-warning"
                          : "status-disabled"
                      }`}
                    >
                      {log.status === "success"
                        ? "Thành công"
                        : log.status === "rate_limited"
                        ? "Rate Limit (429)"
                        : "Thất bại"}
                    </span>
                  </td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>
                    {log.latency_ms !== null ? `${log.latency_ms} ms` : "-"}
                  </td>
                  <td style={{ textAlign: "right", fontWeight: 700 }}>
                    {log.total_tokens !== null ? log.total_tokens.toLocaleString("vi-VN") : "-"}
                  </td>
                  <td>
                    {log.error_type ? (
                      <span
                        style={{
                          fontSize: "11.5px",
                          color: "#dc2626",
                          fontFamily: "monospace",
                        }}
                        title={log.error_type}
                      >
                        {log.error_type}
                        {log.status_code ? ` (${log.status_code})` : ""}
                      </span>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>-</span>
                    )}
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
            Trang <strong>{page}</strong> / {totalPages} (Tổng {total} bản ghi)
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
