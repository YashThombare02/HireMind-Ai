import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/AuthContext";

// Placeholder — real stage-wise dashboard content (score cards, charts,
// trust-score table) is built in Phase 5. This just proves the protected
// route + auth round trip works end to end.
export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="max-w-2xl mx-auto bg-white rounded-lg shadow p-6 flex items-center justify-between">
        <p className="text-slate-800">Welcome, {user?.name}</p>
        <button
          onClick={handleLogout}
          className="text-sm text-slate-600 border border-slate-300 rounded px-3 py-1.5"
        >
          Log out
        </button>
      </div>

      <div className="max-w-2xl mx-auto bg-white rounded-lg shadow p-6 mt-4">
        <p className="text-sm text-slate-600 mb-3">
          Full stage-wise dashboard (scores, charts, trust-score table) arrives in a later phase. For now:
        </p>
        <Link
          to="/resume-upload"
          className="inline-block bg-slate-800 text-white rounded px-4 py-2 text-sm font-medium"
        >
          Upload a resume
        </Link>
      </div>
    </div>
  );
}
