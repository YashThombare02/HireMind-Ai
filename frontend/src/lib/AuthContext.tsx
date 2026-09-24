import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiGet, apiPost, ApiError } from "./api";
import type { User } from "./types";

type Status = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  user: User | null;
  status: Status;
  loginError: string | null;
  signupError: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchAndSetUser(setUser: (u: User) => void) {
  const user = await apiGet<User>("/users/me", true);
  setUser(user);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [signupError, setSignupError] = useState<string | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    if (!token) {
      setStatus("unauthenticated");
      return;
    }
    fetchAndSetUser(setUser)
      .then(() => setStatus("authenticated"))
      .catch(() => {
        sessionStorage.removeItem("token");
        setStatus("unauthenticated");
      });
  }, []);

  async function login(email: string, password: string) {
    setLoginError(null);
    try {
      const { access_token } = await apiPost<{ access_token: string }>("/auth/login", {
        email,
        password,
      });
      sessionStorage.setItem("token", access_token);
      await fetchAndSetUser(setUser);
      setStatus("authenticated");
    } catch (err) {
      setLoginError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
      throw err;
    }
  }

  async function signup(name: string, email: string, password: string) {
    setSignupError(null);
    try {
      await apiPost("/auth/register", { name, email, password });
      // Signing up immediately logs the candidate in, rather than requiring
      // a second manual login step right after they just filled a form.
      await login(email, password);
    } catch (err) {
      setSignupError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
      throw err;
    }
  }

  function logout() {
    sessionStorage.removeItem("token");
    setUser(null);
    setStatus("unauthenticated");
  }

  return (
    <AuthContext.Provider value={{ user, status, loginError, signupError, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
