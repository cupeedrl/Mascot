import { type FormEvent, useState } from "react";
import { BookOpenCheck, BrainCircuit } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PenguinMark } from "../components/PenguinMark";

interface AuthPageProps {
  mode: "login" | "register";
}

export function AuthPage({ mode }: AuthPageProps) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isRegister = mode === "register";

  if (user) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (isRegister && password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      const destination =
        (location.state as { from?: string } | null)?.from ?? "/app";
      navigate(destination, { replace: true });
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        if (caughtError.status === 401) {
          setError("Email hoặc mật khẩu không chính xác.");
        } else if (caughtError.status === 409) {
          setError("Email này đã được đăng ký.");
        } else {
          setError(caughtError.message);
        }
      } else {
        setError("Đã có lỗi xảy ra. Vui lòng thử lại.");
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
        <p className="eyebrow">HỌC TIẾNG ANH CÙNG AI</p>
        <h1 id="brand-heading">Học thông minh hơn, từng từ một.</h1>
        <p>
          Xây dựng vốn từ theo lộ trình rõ ràng, ôn đúng lúc và luyện tập với AI
          trong một không gian học tập thực sự thuộc về bạn.
        </p>
        <div className="auth-benefits" aria-label="Điểm nổi bật">
          <span><BookOpenCheck size={18} /> Lộ trình Tiếng Anh tổng quát theo CEFR</span>
          <span><BrainCircuit size={18} /> AI hỗ trợ, bạn luôn là người quyết định</span>
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
          <p className="eyebrow">{isRegister ? "BẮT ĐẦU HÀNH TRÌNH" : "CHÀO MỪNG TRỞ LẠI"}</p>
          <h2>{isRegister ? "Tạo tài khoản" : "Đăng nhập"}</h2>
          <p className="form-intro">
            {isRegister
              ? "Tạo tài khoản để bắt đầu không gian học tập riêng của bạn."
              : "Tiếp tục hành trình học tập của bạn."}
          </p>

          <form onSubmit={handleSubmit} noValidate>
            <label htmlFor={`${mode}-email`}>Email</label>
            <input
              id={`${mode}-email`}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              maxLength={320}
              placeholder="ban@example.com"
            />

            <div className="field-label-row">
              <label htmlFor={`${mode}-password`}>Mật khẩu</label>
              {!isRegister && (
                <Link className="forgot-password-link" to="/forgot-password">
                  Quên mật khẩu?
                </Link>
              )}
            </div>
            <input
              id={`${mode}-password`}
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={isRegister ? 12 : 1}
              maxLength={128}
              placeholder={isRegister ? "Tối thiểu 12 ký tự" : "Nhập mật khẩu"}
            />

            {isRegister && (
              <>
                <label htmlFor="register-confirm-password">Xác nhận mật khẩu</label>
                <input
                  id="register-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={12}
                  maxLength={128}
                  placeholder="Nhập lại mật khẩu"
                />
              </>
            )}

            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}

            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? "Đang xử lý…"
                : isRegister
                  ? "Tạo tài khoản"
                  : "Đăng nhập"}
            </button>
          </form>

          <p className="auth-switch">
            {isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"}{" "}
            <Link to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Đăng nhập" : "Đăng ký"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
