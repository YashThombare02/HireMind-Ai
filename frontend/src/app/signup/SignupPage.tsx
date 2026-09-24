import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/AuthContext";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function SignupPage() {
  const { signup, signupError } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!name.trim()) errors.name = "Name is required.";
    if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email address.";
    if (password.length < 8) errors.password = "Password must be at least 8 characters.";
    if (password !== confirmPassword) errors.confirmPassword = "Passwords do not match.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      await signup(name, email, password);
      navigate("/dashboard");
    } catch {
      setServerError("signup-error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white rounded-lg shadow p-6 space-y-4">
        <h1 className="text-xl font-semibold text-slate-800">Create your account</h1>

        <div>
          <label className="block text-sm text-slate-600 mb-1" htmlFor="name">
            Name
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
          {fieldErrors.name && <p className="text-red-600 text-xs mt-1">{fieldErrors.name}</p>}
        </div>

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

        <div>
          <label className="block text-sm text-slate-600 mb-1" htmlFor="confirmPassword">
            Confirm password
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
          {fieldErrors.confirmPassword && (
            <p className="text-red-600 text-xs mt-1">{fieldErrors.confirmPassword}</p>
          )}
        </div>

        {serverError && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
            {signupError ?? "Something went wrong. Please try again."}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-slate-800 text-white rounded py-2 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Creating account..." : "Sign up"}
        </button>

        <p className="text-sm text-slate-500 text-center">
          Already have an account?{" "}
          <Link to="/login" className="text-slate-800 underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
