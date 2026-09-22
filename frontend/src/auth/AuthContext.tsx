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
  ) => Promise<void>;
  register: (
    email: string,
    password: string,
    warmupOptions?: BackendWarmupOptions,
  ) => Promise<void>;
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
  ) => {
    const token = await loginRequest(email, password, warmupOptions);
    setAccessToken(token.access_token);
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
    ) => {
      await registerRequest(email, password, warmupOptions);
      await authenticate(email, password, warmupOptions);
    },
    [authenticate],
  );

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
      logout,
    }),
    [
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
