import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import InstallPrompt from "@/components/InstallPrompt";
import BottomNav from "@/components/BottomNav";
import PwaUpdater from "@/components/PwaUpdater";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Pricing from "@/pages/Pricing";
import Dashboard from "@/pages/Dashboard";
import Subscription from "@/pages/Subscription";
import PaymentCallback from "@/pages/PaymentCallback";
import LegalPage from "@/pages/LegalPage";
import AdminLayout, { AdminOverview } from "@/pages/admin/AdminLayout";
import AdminUsers from "@/pages/admin/AdminUsers";
import AdminPayments from "@/pages/admin/AdminPayments";
import AdminConfig from "@/pages/admin/AdminConfig";
import AdminPredictions from "@/pages/admin/AdminPredictions";
import AdminSecurity from "@/pages/admin/AdminSecurity";
import AdminUsage from "@/pages/admin/AdminUsage";

function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#525252] co-pulse">// Loading terminal…</div>
    </div>
  );
  if (!user) return <Navigate to={`/login?next=${loc.pathname}`} replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing/>}/>
          <Route path="/pricing" element={<Pricing/>}/>
          <Route path="/login" element={<Login/>}/>
          <Route path="/register" element={<Register/>}/>
          <Route path="/payment/callback" element={<PaymentCallback/>}/>
          <Route path="/terms" element={<LegalPage type="terms"/>}/>
          <Route path="/privacy" element={<LegalPage type="privacy"/>}/>

          <Route path="/dashboard" element={<ProtectedRoute><Dashboard/></ProtectedRoute>}/>
          <Route path="/subscription" element={<ProtectedRoute><Subscription/></ProtectedRoute>}/>

          <Route path="/admin" element={<ProtectedRoute adminOnly><AdminLayout/></ProtectedRoute>}>
            <Route index element={<AdminOverview/>}/>
            <Route path="users" element={<AdminUsers/>}/>
            <Route path="payments" element={<AdminPayments/>}/>
            <Route path="predictions" element={<AdminPredictions/>}/>
            <Route path="usage" element={<AdminUsage/>}/>
            <Route path="security" element={<AdminSecurity/>}/>
            <Route path="config" element={<AdminConfig/>}/>
          </Route>

          <Route path="*" element={<Navigate to="/" replace/>}/>
        </Routes>
        <InstallPrompt />
        <BottomNav />
        <PwaUpdater />
        <Toaster theme="dark" position="top-center"/>
      </BrowserRouter>
    </AuthProvider>
  );
}
