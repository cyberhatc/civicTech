import { Navigate, Route, Routes } from "react-router-dom";

import AdminDashboard from "@/pages/AdminDashboard";
import CitizenApp from "@/pages/CitizenApp";
import SchemeDetail from "@/pages/SchemeDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CitizenApp />} />
      <Route path="/schemes/:id" element={<SchemeDetail />} />
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
