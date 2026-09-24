import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiPost, ApiError } from "../../lib/api";
import type { AtsResult } from "../../lib/types";

type Status = "loading" | "ready" | "error";

export default function AtsResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { resumeId, jdId } = (location.state as { resumeId?: string; jdId?: string } | null) ?? {};

  const [status, setStatus] = useState<Status>("loading");
  const [result, setResult] = useState<AtsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!resumeId || !jdId) {
      setStatus("error");
      setError("Missing resume or job description — please start over.");
      return;
    }
    apiPost<AtsResult>("/ats/score", { resume_id: resumeId, jd_id: jdId }, true)
      .then((r) => {
        setResult(r);
        setStatus("ready");
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.detail : "Could not compute your match score.");
        setStatus("error");
      });
    // resumeId/jdId are stable for the lifetime of this page (set once from
    // router state on mount) — re-running on their identity is intentional,
    // not a loop risk.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-500">Scoring your match...</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3">
        <p className="text-red-600">{error}</p>
        <Link to="/resume-upload" className="text-slate-800 underline text-sm">
          Start over
        </Link>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="max-w-xl mx-auto bg-white rounded-lg shadow p-6 space-y-5">
        <h1 className="text-xl font-semibold text-slate-800">Your match score</h1>

        <div className="text-center">
          <p className="text-4xl font-semibold text-slate-800">{result.match_score.toFixed(0)}%</p>
          <p className="text-sm text-slate-500 mt-1">{result.recommendation}</p>
        </div>

        <div>
          <h2 className="text-sm font-medium text-slate-700 mb-2">Matched skills</h2>
          <div className="flex flex-wrap gap-2">
            {result.matched_skills.length === 0 && <p className="text-sm text-slate-400">None found.</p>}
            {result.matched_skills.map((skill) => (
              <span key={skill} className="text-xs bg-green-50 text-green-800 border border-green-200 rounded-full px-2.5 py-1">
                {skill}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-sm font-medium text-slate-700 mb-2">Missing skills</h2>
          <div className="flex flex-wrap gap-2">
            {result.missing_skills.length === 0 && <p className="text-sm text-slate-400">None — great match.</p>}
            {result.missing_skills.map((skill) => (
              <span key={skill} className="text-xs bg-red-50 text-red-800 border border-red-200 rounded-full px-2.5 py-1">
                {skill}
              </span>
            ))}
          </div>
        </div>

        <button
          onClick={() => navigate("/dashboard")}
          className="w-full bg-slate-800 text-white rounded py-2 text-sm font-medium"
        >
          Go to dashboard
        </button>
      </div>
    </div>
  );
}
