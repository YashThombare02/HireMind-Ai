import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/AuthContext";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { login, loginError } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [showServerError, setShowServerError] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email address.";
    if (!password) errors.password = "Password is required.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setShowServerError(false);
    if (!validate()) return;

    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch {
      setShowServerError(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white rounded-lg shadow p-6 space-y-4">
        <h1 className="text-xl font-semibold text-slate-800">Log in</h1>

        <div>
          <label className="block text-sm text-slate-600 mb-1" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
          {fieldErrors.email && <p className="text-red-600 text-xs mt-1">{fieldErrors.email}</p>}
        </div>

        <div>
          <label className="block text-sm text-slate-600 mb-1" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
          {fieldErrors.password && <p className="text-red-600 text-xs mt-1">{fieldErrors.password}</p>}
        </div>

        {showServerError && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
            {loginError ?? "Something went wrong. Please try again."}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-slate-800 text-white rounded py-2 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Logging in..." : "Log in"}
        </button>

        <p className="text-sm text-slate-500 text-center">
          Don't have an account?{" "}
          <Link to="/signup" className="text-slate-800 underline">
            Sign up
          </Link>
        </p>
      </form>
    </div>
  );
}
