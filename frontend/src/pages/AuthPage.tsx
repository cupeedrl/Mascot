import { type FormEvent, useEffect, useRef, useState } from "react";
import { BookOpenCheck, BrainCircuit } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError, waitForBackendReady } from "../api/client";
import {
  BackendWarmupTimeoutError,
  isAbortError,
  isTransientBackendUnavailable,
  warmupStatusMessage,
  type BackendWarmupStatus,
} from "../api/backendWarmup";
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
  const [warmupStatus, setWarmupStatus] = useState<
    BackendWarmupStatus | "ready" | "timeout"
  >("connecting");
  const submissionInFlight = useRef(false);
  const submitController = useRef<AbortController | null>(null);
  const isRegister = mode === "register";

  useEffect(() => {
    const controller = new AbortController();
    setWarmupStatus("connecting");
    void waitForBackendReady({
      signal: controller.signal,
      onProgress: ({ status }) => setWarmupStatus(status),
    })
      .then(() => setWarmupStatus("ready"))
      .catch((warmupError: unknown) => {
        if (!isAbortError(warmupError)) setWarmupStatus("timeout");
      });
    return () => {
      controller.abort();
      submitController.current?.abort();
    };
  }, []);

  if (user) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submissionInFlight.current) return;
    setError("");

    if (isRegister && password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    submissionInFlight.current = true;
    setIsSubmitting(true);
    const controller = new AbortController();
    submitController.current = controller;
    const warmupOptions = {
      signal: controller.signal,
      onProgress: ({ status }: { status: BackendWarmupStatus }) =>
        setWarmupStatus(status),
    };
    try {
      if (isRegister) {
        await register(email, password, warmupOptions);
      } else {
        await login(email, password, warmupOptions);
      }
      setWarmupStatus("ready");
      const destination =
        (location.state as { from?: string } | null)?.from ?? "/app";
      navigate(destination, { replace: true });
    } catch (caughtError) {
      if (caughtError instanceof BackendWarmupTimeoutError) {
        setWarmupStatus("timeout");
        setError("Máy chủ mất nhiều thời gian hơn dự kiến. Vui lòng thử lại.");
      } else if (caughtError instanceof ApiError) {
        if (caughtError.code === "ACCOUNT_DISABLED") {
          setError(
            "Tài khoản của bạn hiện đang bị hạn chế. Vui lòng liên hệ quản trị viên để được hỗ trợ.",
          );
        } else if (caughtError.status === 401) {
          setError("Email hoặc mật khẩu không chính xác.");
        } else if (caughtError.status === 409) {
          setError("Email này đã được đăng ký.");
        } else if (isTransientBackendUnavailable(caughtError)) {
          setWarmupStatus("timeout");
          setError("Máy chủ mất nhiều thời gian hơn dự kiến. Vui lòng thử lại.");
        } else {
          setError(caughtError.message);
        }
      } else {
        setError("Đã có lỗi xảy ra. Vui lòng thử lại.");
      }
    } finally {
      submissionInFlight.current = false;
      submitController.current = null;
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
        <h1 id="brand-heading">Học thông minh hơn,<br className="auth-hero-br" />từng từ một.</h1>
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
          <PenguinMark size={170} variant="scholar" />
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

          {warmupStatus !== "ready" && warmupStatus !== "connecting" && (
            <div
              className={`backend-warmup-status${warmupStatus === "timeout" ? " timeout" : ""}`}
              role="status"
              aria-live="polite"
            >
              {warmupStatus !== "timeout" && <span className="mini-spinner" aria-hidden="true" />}
              <span>
                {warmupStatus === "timeout"
                  ? "Máy chủ mất nhiều thời gian hơn dự kiến. Bạn vẫn có thể thử đăng nhập lại."
                  : warmupStatusMessage(warmupStatus)}
              </span>
            </div>
          )}

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
                ? warmupStatus === "starting" || warmupStatus === "almost_ready"
                  ? "Đang khởi động máy chủ…"
                  : "Đang xử lý…"
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
