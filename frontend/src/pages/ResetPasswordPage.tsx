import { type FormEvent, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  KeyRound,
} from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";

import { ApiError, resetPassword } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PenguinMark } from "../components/PenguinMark";

export function ResetPasswordPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  if (user) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!token) {
      setError("Đường dẫn đặt lại mật khẩu không hợp lệ hoặc thiếu mã xác thực.");
      return;
    }
    if (password.length < 12) {
      setError("Mật khẩu mới phải có tối thiểu 12 ký tự.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPassword(token, password, confirmPassword);
      setIsSuccess(true);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Không thể đặt lại mật khẩu. Vui lòng thử lại hoặc yêu cầu liên kết mới.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="brand-panel" aria-labelledby="brand-heading">
        <div className="auth-wordmark">
          <PenguinMark size={42} />
          <strong>Mascot</strong>
        </div>
        <p className="eyebrow">BẢO MẬT TÀI KHOẢN</p>
        <h1 id="brand-heading">Tạo mật khẩu mới an toàn.</h1>
        <p>
          Đặt mật khẩu mạnh với tối thiểu 12 ký tự để bảo vệ tài khoản và tiến trình học tập của bạn.
        </p>
        <div className="auth-benefits" aria-label="Điểm nổi bật">
          <span><BookOpenCheck size={18} /> Mã hóa mật khẩu chuẩn Argon2id bảo mật cao</span>
          <span><BrainCircuit size={18} /> Đăng nhập an toàn trên mọi thiết bị</span>
        </div>
        <div className="brand-mascot-visual" aria-hidden="true">
          <span className="mascot-orbit mascot-orbit-one" />
          <span className="mascot-orbit mascot-orbit-two" />
          <PenguinMark size={170} />
        </div>
      </section>

      <section className="form-panel">
        <div className="auth-card">
          <div className="mobile-auth-brand"><PenguinMark size={32} /> Mascot</div>

          {!token ? (
            <div className="auth-invalid-token" role="alert">
              <div className="auth-invalid-icon">
                <AlertCircle size={28} />
              </div>
              <h2>Liên kết không hợp lệ</h2>
              <p>
                Đường dẫn đặt lại mật khẩu của bạn thiếu mã xác thực hợp lệ hoặc đã bị cắt bớt.
              </p>
              <div className="auth-invalid-actions">
                <Link className="primary-button" to="/forgot-password">
                  Yêu cầu liên kết mới
                </Link>
                <Link className="secondary-link" to="/login">
                  <ArrowLeft size={16} /> Quay lại đăng nhập
                </Link>
              </div>
            </div>
          ) : isSuccess ? (
            <div className="auth-success-box" role="status">
              <div className="auth-success-icon">
                <CheckCircle2 size={28} />
              </div>
              <div>
                <strong>Mật khẩu đã được cập nhật</strong>
                <p>
                  Mật khẩu mới của bạn đã được lưu thành công. Bạn có thể dùng mật khẩu này để đăng nhập ngay bây giờ.
                </p>
              </div>
              <div className="auth-success-actions">
                <Link className="primary-button" to="/login">
                  Đăng nhập ngay
                </Link>
              </div>
            </div>
          ) : (
            <>
              <p className="eyebrow">THAY ĐỔI MẬT KHẨU</p>
              <h2>Đặt lại mật khẩu</h2>
              <p className="form-intro">
                Nhập mật khẩu mới (tối thiểu 12 ký tự) cho tài khoản Mascot của bạn.
              </p>

              <form onSubmit={handleSubmit} noValidate>
                <label htmlFor="reset-new-password">Mật khẩu mới</label>
                <input
                  id="reset-new-password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  minLength={12}
                  maxLength={128}
                  placeholder="Tối thiểu 12 ký tự"
                />

                <label htmlFor="reset-confirm-password">Xác nhận mật khẩu mới</label>
                <input
                  id="reset-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={12}
                  maxLength={128}
                  placeholder="Nhập lại mật khẩu mới"
                />

                {error && (
                  <div className="form-error" role="alert">
                    {error}
                  </div>
                )}

                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  <KeyRound size={17} /> {isSubmitting ? "Đang cập nhật…" : "Đặt lại mật khẩu"}
                </button>
              </form>

              <p className="auth-switch">
                <Link to="/login">
                  <ArrowLeft size={16} /> Quay lại đăng nhập
                </Link>
              </p>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
