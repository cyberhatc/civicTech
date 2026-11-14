import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import CitizenApp from "@/pages/CitizenApp";

// The officer dashboard pulls in the charting library - keep it off the
// critical path so the citizen app loads fast on a rural connection.
const AdminDashboard = lazy(() => import("@/pages/AdminDashboard"));
const SchemeDetail = lazy(() => import("@/pages/SchemeDetail"));

function RouteFallback() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-ink-50">
      <div className="flex flex-col items-center gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-brand-200 border-t-brand-700" />
        <p className="text-sm font-medium text-ink-500">लोड हो रहा है…</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<CitizenApp />} />
        <Route path="/schemes/:id" element={<SchemeDetail />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
