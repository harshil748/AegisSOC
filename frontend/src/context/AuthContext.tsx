import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { login as loginRequest } from "../api/auth";
import { AUTH_EXPIRED_EVENT, ApiError, getToken, setToken } from "../api/client";
import type { AuthUser } from "../types/domain";
import { useToast } from "./ToastContext";

const USER_STORAGE_KEY = "aegis.user";

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const toast = useToast();

  useEffect(() => {
    const token = getToken();
    const storedUser = loadStoredUser();
    if (token && storedUser) {
      setUser(storedUser);
    }
    setIsInitializing(false);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    localStorage.removeItem(USER_STORAGE_KEY);
    setUser(null);
  }, []);

  useEffect(() => {
    const handler = () => {
      if (getToken()) {
        toast.push({
          kind: "error",
          title: "Session expired",
          message: "Your session has expired. Please sign in again.",
        });
      }
      logout();
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await loginRequest(username, password);
      setToken(res.access_token);
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(res.user));
      setUser(res.user);
    } catch (err) {
      if (err instanceof ApiError) {
        throw err;
      }
      throw new Error("Login failed. Please try again.");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isInitializing,
      login,
      logout,
    }),
    [user, isInitializing, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
