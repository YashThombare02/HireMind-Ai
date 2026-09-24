import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AtsResultsPage from "./app/ats-results/AtsResultsPage";
import DashboardPage from "./app/dashboard/DashboardPage";
import JobDescriptionPage from "./app/job-description/JobDescriptionPage";
import LoginPage from "./app/login/LoginPage";
import ResumeUploadPage from "./app/resume-upload/ResumeUploadPage";
import SignupPage from "./app/signup/SignupPage";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./lib/AuthContext";

function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
      <h1 className="text-2xl font-semibold text-slate-800">HireMinds AI</h1>
      <p className="text-slate-600">AI-powered resume, assessment, and interview pipeline.</p>
      <Navigate to="/login" replace />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/resume-upload" element={<ResumeUploadPage />} />
            <Route path="/job-description" element={<JobDescriptionPage />} />
            <Route path="/ats-results" element={<AtsResultsPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
