import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const TOKEN_KEY = "co_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

const client = axios.create({ baseURL: API });
client.interceptors.request.use((cfg) => {
  const t = tokenStore.get();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (detail == null) return err?.message || "Something went wrong";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" · ");
  }
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const api = {
  // Public
  publicConfig: () => client.get("/public/config").then(r => r.data),
  slipToday: () => client.get("/slip/today").then(r => r.data),
  // Auth
  register: (payload) => client.post("/auth/register", payload).then(r => r.data),
  login: (payload) => client.post("/auth/login", payload).then(r => r.data),
  me: () => client.get("/auth/me").then(r => r.data),
  logout: () => client.post("/auth/logout").then(r => r.data),
  // User
  myPayments: () => client.get("/payments/mine").then(r => r.data),
  flwInit: () => client.post("/payments/flutterwave/init", { plan: "monthly", method: "flutterwave" }).then(r => r.data),
  flwVerify: (txRef) => client.post(`/payments/flutterwave/verify?tx_ref=${txRef}`).then(r => r.data),
  bankTransfer: (payload) => client.post("/payments/bank-transfer", payload).then(r => r.data),
  slipHistory: () => client.get("/slip/history").then(r => r.data),
  // Admin
  adminStats: () => client.get("/admin/stats").then(r => r.data),
  adminUsers: () => client.get("/admin/users").then(r => r.data),
  adminGrant: (id, days = 30) => client.post(`/admin/users/${id}/grant?days=${days}`).then(r => r.data),
  adminSuspend: (id) => client.post(`/admin/users/${id}/suspend`).then(r => r.data),
  adminPayments: (status = "all") => client.get(`/admin/payments?status_filter=${status}`).then(r => r.data),
  adminApprove: (id, note = "") => client.post(`/admin/payments/${id}/approve?note=${encodeURIComponent(note)}`).then(r => r.data),
  adminReject: (id, note = "") => client.post(`/admin/payments/${id}/reject?note=${encodeURIComponent(note)}`).then(r => r.data),
  adminConfig: () => client.get("/admin/config").then(r => r.data),
  adminSaveConfig: (cfg) => client.post("/admin/config", cfg).then(r => r.data),
  adminPredictions: (date) => client.get(`/admin/predictions${date ? `?date=${date}` : ""}`).then(r => r.data),
  adminSettle: (id, result) => client.post(`/admin/predictions/${id}/settle`, { result }).then(r => r.data),
  adminGenerate: (force = false) => client.post(`/slip/generate?force=${force}`).then(r => r.data),
  adminRejected: (date) => client.get(`/admin/rejected${date ? `?date=${date}` : ""}`).then(r => r.data),
};
