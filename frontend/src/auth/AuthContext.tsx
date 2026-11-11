import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getCurrentUser,
  hasAccessToken,
  login as loginRequest,
  verifyEmail as verifyEmailRequest,
  type RegisterProfile,
  logout as logoutRequest,
  register as registerRequest,
  setAccessToken,
  setUnauthorizedHandler,
  type User,
} from "../api/client";
import {
  isAbortError,
  shouldClearAuthenticationOnRestoreFailure,
  type BackendWarmupOptions,
  type BackendWarmupStatus,
} from "../api/backendWarmup";

interface AuthContextValue {
  user: User | null;
  isInitializing: boolean;
  restoreUnavailable: boolean;
  restoreStatus: BackendWarmupStatus | null;
  retryRestore: () => Promise<void>;
  login: (
    email: string,
    password: string,
    warmupOptions?: BackendWarmupOptions,
    rememberMe?: boolean,
  ) => Promise<void>;
  register: (
    email: string,
    password: string,
    warmupOptions?: BackendWarmupOptions,
    profile?: RegisterProfile,
  ) => Promise<{ verificationRequired: boolean; email: string }>;
  verifyEmail: (email: string, code: string, rememberMe?: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [restoreUnavailable, setRestoreUnavailable] = useState(false);
  const [restoreStatus, setRestoreStatus] = useState<BackendWarmupStatus | null>(null);
  const restoreController = useRef<AbortController | null>(null);

  const clearAuthentication = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setRestoreUnavailable(false);
  }, []);

  const restoreAuthentication = useCallback(async () => {
    restoreController.current?.abort();
    if (!hasAccessToken()) {
      setRestoreUnavailable(false);
      setRestoreStatus(null);
      setIsInitializing(false);
      return;
    }

    const controller = new AbortController();
    restoreController.current = controller;
    setIsInitializing(true);
    setRestoreUnavailable(false);
    setRestoreStatus("connecting");
    try {
      const currentUser = await getCurrentUser({
        signal: controller.signal,
        onProgress: ({ status }) => setRestoreStatus(status),
      });
      if (!controller.signal.aborted) {
        setUser(currentUser);
        setRestoreStatus(null);
      }
    } catch (error) {
      if (controller.signal.aborted || isAbortError(error)) return;
      if (shouldClearAuthenticationOnRestoreFailure(error)) {
        clearAuthentication();
        setRestoreStatus(null);
      } else {
        // Keep the stored JWT until the backend explicitly rejects it.
        setRestoreUnavailable(true);
      }
    } finally {
      if (!controller.signal.aborted) setIsInitializing(false);
    }
  }, [clearAuthentication]);

  useEffect(() => {
    setUnauthorizedHandler(clearAuthentication);
    void restoreAuthentication();
    return () => {
      restoreController.current?.abort();
      setUnauthorizedHandler(null);
    };
  }, [clearAuthentication, restoreAuthentication]);

  const authenticate = useCallback(async (
    email: string,
    password: string,
    warmupOptions: BackendWarmupOptions = {},
    rememberMe = false,
  ) => {
    const token = await loginRequest(email, password, warmupOptions, rememberMe);
    setAccessToken(token.access_token, rememberMe);
    try {
      const currentUser = await getCurrentUser(warmupOptions);
      setUser(currentUser);
    } catch (error) {
      if (shouldClearAuthenticationOnRestoreFailure(error)) setAccessToken(null);
      throw error;
    }
  }, []);

  const register = useCallback(
    async (
      email: string,
      password: string,
      warmupOptions: BackendWarmupOptions = {},
      profile: RegisterProfile = {},
    ): Promise<{ verificationRequired: boolean; email: string }> => {
      const created = await registerRequest(email, password, warmupOptions, profile);
      if (created.verification_required) {
        return { verificationRequired: true, email: created.email };
      }
      await authenticate(email, password, warmupOptions);
      return { verificationRequired: false, email: created.email };
    },
    [authenticate],
  );

  const verifyEmail = useCallback(async (email: string, code: string, rememberMe = false) => {
    const token = await verifyEmailRequest(email, code, rememberMe);
    setAccessToken(token.access_token, rememberMe);
    try {
      setUser(await getCurrentUser());
    } catch (error) {
      if (shouldClearAuthenticationOnRestoreFailure(error)) setAccessToken(null);
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      if (user) {
        await logoutRequest();
      }
    } finally {
      clearAuthentication();
    }
  }, [clearAuthentication, user]);

  const value = useMemo(
    () => ({
      user,
      isInitializing,
      restoreUnavailable,
      restoreStatus,
      retryRestore: restoreAuthentication,
      login: authenticate,
      register,
      verifyEmail,
      logout,
    }),
    [
      verifyEmail,
      authenticate,
      isInitializing,
      logout,
      register,
      restoreAuthentication,
      restoreStatus,
      restoreUnavailable,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
