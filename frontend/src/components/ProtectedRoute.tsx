import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

export default function ProtectedRoute() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-500">Loading...</p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
