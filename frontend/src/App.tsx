import { useEffect, useState } from "react";
import { apiGet } from "./lib/api";

type HealthResponse = { status: string };

export default function App() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "unreachable">(
    "checking",
  );

  useEffect(() => {
    apiGet<HealthResponse>("/health")
      .then((data) => setBackendStatus(data.status === "ok" ? "connected" : "unreachable"))
      .catch(() => setBackendStatus("unreachable"));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
      <h1 className="text-2xl font-semibold text-slate-800">HireMinds AI</h1>
      <p className="text-slate-600">
        Backend status:{" "}
        <span
          className={
            backendStatus === "connected"
              ? "text-green-600 font-medium"
              : backendStatus === "unreachable"
                ? "text-red-600 font-medium"
                : "text-slate-500"
          }
        >
          {backendStatus}
        </span>
      </p>
      <p className="text-sm text-slate-400">Phase 0 scaffold — pages are added in later phases.</p>
    </div>
  );
}
