import { type FormEvent, useState } from "react";
import { ArrowLeft, BookOpenCheck, BrainCircuit, CheckCircle2, Mail } from "lucide-react";
import { Link, Navigate } from "react-router-dom";

import { ApiError, forgotPassword } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PenguinMark } from "../components/PenguinMark";

export function ForgotPasswordPage() {
  const { user } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Vui lòng nhập địa chỉ email.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await forgotPassword(email.trim());
      setSubmittedMessage(
        response.message ||
          "Nếu email này đã được đăng ký, Mascot sẽ gửi hướng dẫn đặt lại mật khẩu.",
      );
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
      } else {
        setError("Đã có lỗi xảy ra. Vui lòng thử lại sau.");
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
        <p className="eyebrow">KHÔI PHỤC TÀI KHOẢN</p>
        <h1 id="brand-heading">Đừng lo, đã có Mascot đây rồi!</h1>
        <p>
          Chúng tôi sẽ gửi liên kết an toàn đến hòm thư của bạn để bạn có thể tạo
          mật khẩu mới và tiếp tục hành trình học tập.
        </p>
        <div className="auth-benefits" aria-label="Điểm nổi bật">
          <span><BookOpenCheck size={18} /> Liên kết xác thực an toàn, sử dụng một lần</span>
          <span><BrainCircuit size={18} /> Bảo mật thông tin tài khoản cá nhân</span>
        </div>
        <div className="brand-mascot-visual" aria-hidden="true">
          <span className="mascot-orbit mascot-orbit-one" />
          <span className="mascot-orbit mascot-orbit-two" />
          <PenguinMark size={170} variant="scholar" />
        </div>
      </section>

      <section className="form-panel">
        <div className="auth-card">
          <div className="mobile-auth-brand"><PenguinMark size={32} /> Mascot</div>
          <Link className="back-link auth-back-link" to="/login">
            <ArrowLeft size={16} /> Quay lại đăng nhập
          </Link>
          <p className="eyebrow">ĐẶT LẠI MẬT KHẨU</p>
          <h2>Quên mật khẩu?</h2>
          <p className="form-intro">
            Nhập địa chỉ email đăng ký tài khoản Mascot để nhận hướng dẫn đặt lại mật khẩu.
          </p>

          {submittedMessage ? (
            <div className="auth-success-box" role="status">
              <div className="auth-success-icon">
                <CheckCircle2 size={24} />
              </div>
              <div>
                <strong>Kiểm tra hòm thư của bạn</strong>
                <p>{submittedMessage}</p>
                <small>
                  Nếu không thấy email trong vài phút, hãy kiểm tra mục Thư rác (Spam) hoặc thử lại.
                </small>
              </div>
              <div className="auth-success-actions">
                <Link className="primary-button" to="/login">
                  Quay lại đăng nhập
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              <label htmlFor="forgot-email">Email đăng ký</label>
              <input
                id="forgot-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                maxLength={320}
                placeholder="ban@example.com"
              />

              {error && (
                <div className="form-error" role="alert">
                  {error}
                </div>
              )}

              <button className="primary-button" type="submit" disabled={isSubmitting}>
                <Mail size={17} /> {isSubmitting ? "Đang gửi…" : "Gửi hướng dẫn đặt lại mật khẩu"}
              </button>
            </form>
          )}

          <p className="auth-switch">
            Nhớ mật khẩu rồi? <Link to="/login">Đăng nhập ngay</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
