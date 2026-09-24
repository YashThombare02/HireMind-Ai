import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiPost, ApiError } from "../../lib/api";
import type { JobDescription } from "../../lib/types";

const MIN_LENGTH = 50;
const MAX_LENGTH = 10_000;

export default function JobDescriptionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const resumeId = (location.state as { resumeId?: string } | null)?.resumeId;

  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (text.trim().length < MIN_LENGTH) {
      setError(`Please paste a fuller job description (at least ${MIN_LENGTH} characters).`);
      return;
    }
    if (!resumeId) {
      setError("Missing your uploaded resume — please upload a resume first.");
      return;
    }

    setSubmitting(true);
    try {
      const jd = await apiPost<JobDescription>("/job-descriptions", { raw_text: text }, true);
      navigate("/ats-results", { state: { resumeId, jdId: jd.id } });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <form onSubmit={handleSubmit} className="max-w-xl mx-auto bg-white rounded-lg shadow p-6 space-y-4">
        <h1 className="text-xl font-semibold text-slate-800">Paste the job description</h1>

        <div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            placeholder="Paste the full job description here..."
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
          <p className="text-xs text-slate-400 mt-1">
            {text.length} / {MAX_LENGTH} characters
          </p>
        </div>

        {error && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-slate-800 text-white rounded py-2 text-sm font-medium disabled:opacity-50"
        >
          {submitting ? "Analyzing..." : "Continue"}
        </button>
      </form>
    </div>
  );
}
