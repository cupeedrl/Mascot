import {
  type ClipboardEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { Check, Eye, EyeOff, Loader2, Lock, Mail, User as UserIcon, X } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError, checkUsername, resendVerification, waitForBackendReady } from "../api/client";
import {
  BackendWarmupTimeoutError,
  isAbortError,
  isTransientBackendUnavailable,
  warmupStatusMessage,
  type BackendWarmupStatus,
} from "../api/backendWarmup";
import { useAuth } from "../auth/AuthContext";
import { PenguinMark } from "../components/PenguinMark";
import {
  USERNAME_RULE,
  cleanCode,
  formatCountdown,
  isValidUsername,
  normalizeUsername,
  passwordStrength,
} from "../features/auth/authForm";

interface AuthPageProps {
  mode: "login" | "register";
}

type UsernameState = "idle" | "checking" | "available" | "taken" | "invalid" | "reserved";

const RESEND_SECONDS = 60;
const SERVER_SLOW = "Máy chủ mất nhiều thời gian hơn dự kiến. Hãy thử lại.";

function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  placeholder: string;
}) {
  const [visible, setVisible] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const detectCaps = (event: KeyboardEvent<HTMLInputElement>) =>
    setCapsLock(event.getModifierState?.("CapsLock") ?? false);
  return (
    <>
      <div className="auth-input">
        <Lock size={17} aria-hidden="true" />
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyUp={detectCaps}
          onKeyDown={detectCaps}
          maxLength={128}
          placeholder={placeholder}
          required
        />
        <button
          type="button"
          className="auth-input-action"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
        >
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
      {capsLock && <p className="auth-hint warning">Caps Lock đang bật</p>}
    </>
  );
}

function CodeInput({ value, onChange, disabled }: { value: string; onChange: (code: string) => void; disabled: boolean }) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  // Keystrokes can arrive faster than React re-renders, so edit the latest value.
  const latest = useRef(value);
  latest.current = value;
  // Empty boxes are kept as spaces so later digits stay in their own box.
  const toDigits = (code: string) => Array.from({ length: 6 }, (_, i) => (code[i] ?? "").trim());
  const digits = toDigits(value);

  function setDigit(index: number, raw: string) {
    const typed = cleanCode(raw);
    const current = toDigits(latest.current);
    // Typing into a filled box replaces its digit; several digits (autofill) spread out.
    const incoming = typed.length > 1 && current[index] && typed.startsWith(current[index]) ? typed.slice(1) : typed;
    if (!incoming) current[index] = "";
    incoming.split("").forEach((digit, offset) => {
      if (index + offset < 6) current[index + offset] = digit;
    });
    const next = current.map((digit) => digit || " ").join("").trimEnd();
    latest.current = next;
    onChange(next);
    if (incoming) refs.current[Math.min(index + incoming.length, 5)]?.focus();
  }

  function onKey(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !digits[index] && index > 0) refs.current[index - 1]?.focus();
    if (event.key === "ArrowLeft" && index > 0) refs.current[index - 1]?.focus();
    if (event.key === "ArrowRight" && index < 5) refs.current[index + 1]?.focus();
  }

  function onPaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = cleanCode(event.clipboardData.getData("text"));
    if (!pasted) return;
    event.preventDefault();
    onChange(pasted);
    refs.current[Math.min(pasted.length, 5)]?.focus();
  }

  return (
    <div className="auth-code" role="group" aria-label="Mã xác nhận 6 số">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(element) => {
            refs.current[index] = element;
          }}
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          aria-label={`Số thứ ${index + 1}`}
          onFocus={(event) => event.target.select()}
          value={digit}
          disabled={disabled}
          onChange={(event) => setDigit(index, event.target.value)}
          onKeyDown={(event) => onKey(index, event)}
          onPaste={onPaste}
          autoFocus={index === 0}
        />
      ))}
    </div>
  );
}

export function AuthPage({ mode }: AuthPageProps) {
  const { user, login, register, verifyEmail } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isRegister = mode === "register";

  const [step, setStep] = useState<"form" | "verify">("form");
  const [identifier, setIdentifier] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [usernameState, setUsernameState] = useState<UsernameState>("idle");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [verifyEmailAddress, setVerifyEmailAddress] = useState("");
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [warmupStatus, setWarmupStatus] = useState<BackendWarmupStatus | "ready" | "timeout">("connecting");
  const submissionInFlight = useRef(false);
  const submitController = useRef<AbortController | null>(null);
  const strength = passwordStrength(password);

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

  useEffect(() => {
    setStep("form");
    setError("");
    setNotice("");
  }, [mode]);

  // Ask the server whether the username is free, shortly after typing stops.
  useEffect(() => {
    if (!isRegister || !username.trim()) {
      setUsernameState("idle");
      return;
    }
    if (!isValidUsername(username)) {
      setUsernameState("invalid");
      return;
    }
    setUsernameState("checking");
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      checkUsername(normalizeUsername(username), controller.signal)
        .then((result) => setUsernameState(result.available ? "available" : (result.reason ?? "invalid")))
        .catch(() => setUsernameState("idle"));
    }, 400);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [username, isRegister]);

  // Submit by itself once all six digits are in.
  useEffect(() => {
    if (step === "verify" && /^\d{6}$/.test(code) && !submissionInFlight.current) handleVerify();
  }, [code, step]);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = window.setTimeout(() => setResendIn((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendIn]);

  if (user) {
    return <Navigate to="/app" replace />;
  }

  function goToApp() {
    const destination = (location.state as { from?: string } | null)?.from ?? "/app";
    navigate(destination, { replace: true });
  }

  function openVerifyStep(address: string, sendNewCode: boolean) {
    setVerifyEmailAddress(address);
    setCode("");
    setStep("verify");
    setResendIn(RESEND_SECONDS);
    if (sendNewCode) void resendVerification(address).catch(() => undefined);
  }

  function describeError(caughtError: unknown): string {
    if (caughtError instanceof BackendWarmupTimeoutError) {
      setWarmupStatus("timeout");
      return SERVER_SLOW;
    }
    if (caughtError instanceof ApiError) {
      if (caughtError.code === "ACCOUNT_DISABLED") {
        return "Tài khoản của bạn hiện đang bị hạn chế. Hãy liên hệ quản trị viên để được hỗ trợ.";
      }
      if (caughtError.code === "USERNAME_TAKEN") return "Tên người dùng này đã có người dùng.";
      if (caughtError.status === 401) return "Email, tên người dùng hoặc mật khẩu không đúng.";
      if (caughtError.status === 409) return "Email này đã được đăng ký. Hãy đăng nhập.";
      if (isTransientBackendUnavailable(caughtError)) {
        setWarmupStatus("timeout");
        return SERVER_SLOW;
      }
      return caughtError.message;
    }
    return "Đã có lỗi xảy ra. Hãy thử lại.";
  }

  async function runSubmission(work: (options: { signal: AbortSignal; onProgress: (p: { status: BackendWarmupStatus }) => void }) => Promise<void>) {
    if (submissionInFlight.current) return;
    submissionInFlight.current = true;
    setIsSubmitting(true);
    setError("");
    setNotice("");
    const controller = new AbortController();
    submitController.current = controller;
    try {
      await work({ signal: controller.signal, onProgress: ({ status }) => setWarmupStatus(status) });
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.code === "EMAIL_NOT_VERIFIED") {
        openVerifyStep(caughtError.detail?.email ?? identifier.trim(), true);
        setNotice("Tài khoản chưa xác nhận email. Mascot vừa gửi một mã mới cho bạn.");
      } else {
        setError(describeError(caughtError));
      }
    } finally {
      submissionInFlight.current = false;
      submitController.current = null;
      setIsSubmitting(false);
    }
  }

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identifier.trim() || !password) {
      setError("Hãy nhập email hoặc tên người dùng và mật khẩu.");
      return;
    }
    void runSubmission(async (options) => {
      await login(identifier.trim(), password, options, rememberMe);
      setWarmupStatus("ready");
      goToApp();
    });
  }

  function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!displayName.trim()) return setError("Hãy nhập tên hiển thị.");
    if (!isValidUsername(username)) return setError(`Tên người dùng chưa hợp lệ: ${USERNAME_RULE}`);
    if (usernameState === "taken") return setError("Tên người dùng này đã có người dùng.");
    if (usernameState === "reserved") return setError("Tên người dùng này đã được hệ thống giữ lại.");
    if (!email.trim()) return setError("Hãy nhập email.");
    if (!strength.meetsMinimum) return setError("Mật khẩu cần tối thiểu 12 ký tự.");
    void runSubmission(async (options) => {
      const result = await register(email.trim(), password, options, {
        display_name: displayName.trim(),
        username: normalizeUsername(username),
      });
      setWarmupStatus("ready");
      if (result.verificationRequired) openVerifyStep(result.email, false);
      else goToApp();
    });
  }

  function handleVerify(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("Hãy nhập đủ 6 số.");
      return;
    }
    void runSubmission(async () => {
      try {
        await verifyEmail(verifyEmailAddress, code, rememberMe);
      } catch (caughtError) {
        if (caughtError instanceof ApiError && caughtError.code === "ALREADY_VERIFIED") {
          navigate("/login", { replace: true });
          return;
        }
        if (caughtError instanceof ApiError && caughtError.detail?.code) {
          const remaining = caughtError.detail.remaining_attempts;
          setCode("");
          throw new ApiError(
            caughtError.status,
            remaining && caughtError.code === "INVALID_CODE"
              ? `${caughtError.message} Bạn còn ${remaining} lần thử.`
              : caughtError.message,
          );
        }
        throw caughtError;
      }
      goToApp();
    });
  }

  async function handleResend() {
    if (resendIn > 0) return;
    setError("");
    try {
      await resendVerification(verifyEmailAddress);
      setNotice(`Đã gửi mã mới tới ${verifyEmailAddress}.`);
      setCode("");
      setResendIn(RESEND_SECONDS);
    } catch (caughtError) {
      setError(describeError(caughtError));
    }
  }

  const usernameHint: Record<UsernameState, { text: string; tone: string } | null> = {
    idle: { text: USERNAME_RULE, tone: "" },
    checking: { text: "Đang kiểm tra…", tone: "" },
    available: { text: "Tên này còn trống", tone: "success" },
    taken: { text: "Tên này đã có người dùng", tone: "danger" },
    reserved: { text: "Tên này đã được hệ thống giữ lại", tone: "danger" },
    invalid: { text: USERNAME_RULE, tone: "danger" },
  };
  const hint = usernameHint[usernameState];
  const busyLabel =
    warmupStatus === "starting" || warmupStatus === "almost_ready" ? "Đang khởi động máy chủ…" : "Đang xử lý…";

  return (
    <main className="auth-layout auth-layout-v2">
      <section className="brand-panel brand-panel-v2" aria-labelledby="brand-heading">
        <div className="auth-wordmark">
          <PenguinMark size={40} />
          <strong>Mascot</strong>
        </div>
        <p className="eyebrow">Học từ vựng cùng AI</p>
        <h1 id="brand-heading">Học thông minh hơn,<br className="auth-hero-br" />từng từ một.</h1>
        <p>Tiếng Anh theo CEFR, tiếng Trung theo HSK 3.0. Ôn đúng lúc, luyện tập cùng trợ lý AI.</p>
        <div className="auth-word-card" aria-hidden="true">
          <div className="auth-word-card-top">
            <strong lang="zh">学习</strong>
            <span>HSK 1</span>
          </div>
          <small>xuéxí · Động từ</small>
          <p>học tập</p>
        </div>
        <ul className="auth-facts" aria-label="Mascot có gì">
          <li><b>10.999</b> từ HSK 1–9</li>
          <li><b>6</b> cấp CEFR</li>
          <li><b>AI</b> hỗ trợ luyện tập</li>
        </ul>
      </section>

      <section className="form-panel">
        <div className="auth-card auth-card-v2">
          <div className="mobile-auth-brand"><PenguinMark size={32} /> Mascot</div>

          {warmupStatus !== "ready" && warmupStatus !== "connecting" && (
            <div className={`backend-warmup-status${warmupStatus === "timeout" ? " timeout" : ""}`} role="status" aria-live="polite">
              {warmupStatus !== "timeout" && <span className="mini-spinner" aria-hidden="true" />}
              <span>
                {warmupStatus === "timeout"
                  ? "Máy chủ mất nhiều thời gian hơn dự kiến. Bạn vẫn có thể thử lại."
                  : warmupStatusMessage(warmupStatus)}
              </span>
            </div>
          )}

          {step === "verify" ? (
            <>
              <p className="eyebrow">{isRegister ? "Bước 2/2" : "Xác nhận tài khoản"}</p>
              <h2>Xác nhận email</h2>
              <p className="form-intro">
                Mascot đã gửi mã 6 số tới <strong>{verifyEmailAddress}</strong>. Mã có hiệu lực trong 10 phút.
              </p>
              {notice && <div className="success-banner" role="status">{notice}</div>}
              <form onSubmit={handleVerify} noValidate>
                <CodeInput value={code} onChange={setCode} disabled={isSubmitting} />
                {error && <div className="form-error" role="alert">{error}</div>}
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Đang xác nhận…" : "Xác nhận và bắt đầu học"}
                </button>
              </form>
              <p className="auth-switch">
                Chưa nhận được mã?{" "}
                {resendIn > 0 ? (
                  <span className="auth-muted">Gửi lại sau {formatCountdown(resendIn)}</span>
                ) : (
                  <button type="button" className="text-button" onClick={() => void handleResend()}>Gửi lại mã</button>
                )}
                {" · "}
                <button type="button" className="text-button" onClick={() => { setStep("form"); setError(""); setNotice(""); }}>
                  {isRegister ? "Đổi email" : "Quay lại đăng nhập"}
                </button>
              </p>
            </>
          ) : isRegister ? (
            <>
              <p className="eyebrow">Bước 1/2</p>
              <h2>Tạo tài khoản</h2>
              <p className="form-intro">Chỉ mất một phút. Mascot sẽ gửi mã xác nhận tới email của bạn.</p>
              <form onSubmit={handleRegister} noValidate>
                <label htmlFor="register-name">Tên hiển thị</label>
                <div className="auth-input">
                  <UserIcon size={17} aria-hidden="true" />
                  <input id="register-name" autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={80} placeholder="Nguyễn Văn An" required />
                </div>

                <label htmlFor="register-username">Tên người dùng</label>
                <div className={`auth-input${hint?.tone === "danger" ? " invalid" : ""}`}>
                  <span className="auth-input-prefix" aria-hidden="true">@</span>
                  <input id="register-username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value.replace(/\s/g, ""))} maxLength={30} placeholder="an.nguyen" required aria-describedby="register-username-hint" />
                  {usernameState === "checking" && <Loader2 className="auth-spin" size={16} aria-hidden="true" />}
                  {usernameState === "available" && <Check className="auth-ok" size={16} aria-hidden="true" />}
                  {(usernameState === "taken" || usernameState === "reserved") && <X className="auth-bad" size={16} aria-hidden="true" />}
                </div>
                {hint && <p id="register-username-hint" className={`auth-hint ${hint.tone}`}>{hint.text}</p>}

                <label htmlFor="register-email">Email</label>
                <div className="auth-input">
                  <Mail size={17} aria-hidden="true" />
                  <input id="register-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={320} placeholder="ban@example.com" required />
                </div>

                <label htmlFor="register-password">Mật khẩu</label>
                <PasswordField id="register-password" value={password} onChange={setPassword} autoComplete="new-password" placeholder="Tối thiểu 12 ký tự" />
                {password && (
                  <div className="auth-strength" aria-live="polite">
                    <div className={`auth-strength-bar score-${strength.score}`}>
                      {[1, 2, 3, 4].map((level) => <span key={level} className={strength.score >= level ? "on" : ""} />)}
                    </div>
                    <small>{strength.label}{strength.meetsMinimum ? "" : " · cần tối thiểu 12 ký tự"}</small>
                  </div>
                )}

                {error && <div className="form-error" role="alert">{error}</div>}
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? busyLabel : "Tiếp tục"}
                </button>
              </form>
              <p className="auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
            </>
          ) : (
            <>
              <p className="eyebrow">Chào mừng trở lại</p>
              <h2>Đăng nhập</h2>
              <p className="form-intro">Tiếp tục hành trình học của bạn.</p>
              <form onSubmit={handleLogin} noValidate>
                <label htmlFor="login-identifier">Email hoặc tên người dùng</label>
                <div className="auth-input">
                  <UserIcon size={17} aria-hidden="true" />
                  <input id="login-identifier" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} maxLength={320} placeholder="ban@example.com" required />
                </div>
                <div className="field-label-row">
                  <label htmlFor="login-password">Mật khẩu</label>
                  <Link className="forgot-password-link" to="/forgot-password">Quên mật khẩu?</Link>
                </div>
                <PasswordField id="login-password" value={password} onChange={setPassword} autoComplete="current-password" placeholder="Nhập mật khẩu" />
                <label className="auth-remember">
                  <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
                  <span>Ghi nhớ đăng nhập trong 30 ngày</span>
                </label>
                {error && <div className="form-error" role="alert">{error}</div>}
                <button className="primary-button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? busyLabel : "Đăng nhập"}
                </button>
              </form>
              <p className="auth-switch">Chưa có tài khoản? <Link to="/register">Tạo tài khoản</Link></p>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
