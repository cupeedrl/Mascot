import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  setAccessToken,
  setUnauthorizedHandler,
  type User,
} from "../api/client";

interface AuthContextValue {
  user: User | null;
  isInitializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const clearAuthentication = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(clearAuthentication);
    setIsInitializing(false);
    return () => setUnauthorizedHandler(null);
  }, [clearAuthentication]);

  const authenticate = useCallback(async (email: string, password: string) => {
    const token = await loginRequest(email, password);
    setAccessToken(token.access_token);
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      setAccessToken(null);
      throw error;
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await registerRequest(email, password);
      await authenticate(email, password);
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
    () => ({ user, isInitializing, login: authenticate, register, logout }),
    [authenticate, isInitializing, logout, register, user],
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
