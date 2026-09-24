import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiPatch, apiUpload, ApiError } from "../../lib/api";
import type { Resume } from "../../lib/types";

const MAX_SIZE_BYTES = 5 * 1024 * 1024;

type Status = "idle" | "uploading" | "error" | "review";

export default function ResumeUploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [skillsText, setSkillsText] = useState("");

  function preCheck(file: File): string | null {
    if (file.type !== "application/pdf") return "Please upload a PDF file.";
    if (file.size > MAX_SIZE_BYTES) return "File is larger than 5MB.";
    return null;
  }

  async function handleFile(file: File) {
    const precheckError = preCheck(file);
    if (precheckError) {
      setStatus("error");
      setErrorMessage(precheckError);
      return;
    }

    setStatus("uploading");
    setErrorMessage(null);
    try {
      const uploaded = await apiUpload<Resume>("/resumes/upload", file);
      setResume(uploaded);
      setSkillsText(uploaded.skills.join(", "));
      setStatus("review");
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.detail : "Upload failed. Please try again.");
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  async function handleConfirm() {
    if (!resume) return;
    const skills = skillsText
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    try {
      await apiPatch<Resume>(`/resumes/${resume.id}`, { skills }, true);
    } catch {
      // Non-fatal — proceed with whatever was already parsed rather than
      // blocking the flow over a correction save failing.
    }
    navigate("/job-description", { state: { resumeId: resume.id } });
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="max-w-xl mx-auto bg-white rounded-lg shadow p-6 space-y-4">
        <h1 className="text-xl font-semibold text-slate-800">Upload your resume</h1>

        {status !== "review" && (
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-slate-300 rounded-lg p-10 text-center cursor-pointer hover:border-slate-400"
          >
            <p className="text-slate-500 text-sm">
              {status === "uploading" ? "Uploading and parsing..." : "Drag & drop a PDF here, or click to choose one"}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
              }}
            />
          </div>
        )}

        {status === "error" && errorMessage && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">
            {errorMessage}
          </p>
        )}

        {status === "review" && resume && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Here's what we found — fix anything that looks wrong before continuing.
            </p>

            <div>
              <label className="block text-sm text-slate-600 mb-1">Skills (comma-separated)</label>
              <textarea
                value={skillsText}
                onChange={(e) => setSkillsText(e.target.value)}
                rows={3}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              />
            </div>

            <div className="text-sm text-slate-600 space-y-1">
              <p>{resume.education.length} education entries, {resume.experience.length} experience entries, {resume.projects.length} projects, {resume.certifications.length} certifications parsed.</p>
            </div>

            <button
              onClick={handleConfirm}
              className="w-full bg-slate-800 text-white rounded py-2 text-sm font-medium"
            >
              Confirm and continue
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
