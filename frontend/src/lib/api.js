import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "");
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
  publicRoi: (days = 30) => client.get(`/public/roi?days=${days}`).then(r => r.data),
  scheduleUpcoming: (date) => client.get(date ? `/schedule/upcoming?date=${date}` : `/schedule/upcoming?days=3`).then(r => r.data),
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
  adminGenerate: (force = false, date = "today") => client.post(`/slip/generate?force=${force}&date=${date}`).then(r => r.data),
  adminGenerateStatus: (jobId) => client.get(`/slip/generate/status/${jobId}`).then(r => r.data),
  adminRejected: (date) => client.get(`/admin/rejected${date ? `?date=${date}` : ""}`).then(r => r.data),
  adminGetSlipCode: (date) => client.get(`/admin/slip/code${date ? `?date=${date}` : ""}`).then(r => r.data),
  adminSetSlipCode: (code, date) => client.post(`/admin/slip/code`, { code, date }).then(r => r.data),
  // Push
  pushSubscribe: (subscription) => client.post(`/push/subscribe`, { subscription }).then(r => r.data),
  pushUnsubscribe: (endpoint) => client.post(`/push/unsubscribe`, { endpoint }).then(r => r.data),
  adminPushTest: (title, body) => client.post(`/admin/push/test`, { title, body }).then(r => r.data),
  adminApifootballPreflight: () => client.get(`/admin/apifootball/preflight`).then(r => r.data),
  adminApibasketballPreflight: () => client.get(`/admin/apibasketball/preflight`).then(r => r.data),
  adminSettleNow: () => client.post(`/admin/settle/now`).then(r => r.data),
  adminScheduleSync: () => client.post(`/admin/schedule/sync`).then(r => r.data),
  adminScheduleHeal: () => client.post(`/admin/schedule/heal`).then(r => r.data),
  adminUsage: () => client.get(`/admin/usage`).then(r => r.data),
  adminApiBasketballDiagnostic: () => client.get(`/admin/apibasketball/diagnostic`).then(r => r.data),
  // Phase 7 — security + email
  changePassword: (current_password, new_password) =>
    client.post(`/auth/password/change`, { current_password, new_password }).then(r => r.data),
  myActivity: (limit = 20) => client.get(`/auth/activity?limit=${limit}`).then(r => r.data),
  adminActivity: (limit = 100, userId) =>
    client.get(`/admin/activity?limit=${limit}${userId ? `&user_id=${userId}` : ""}`).then(r => r.data),
  adminSmtpTest: () => client.post(`/admin/smtp/test`).then(r => r.data),
  adminSmtpSendTest: (to) => client.post(`/admin/smtp/send-test`, { to: to || "" }).then(r => r.data),
  adminEmailLogs: (limit = 100) => client.get(`/admin/emails/logs?limit=${limit}`).then(r => r.data),
  // Referrals
  referralMe: () => client.get(`/referral/me`).then(r => r.data),
  referralValidate: (code) => client.get(`/referral/validate?code=${encodeURIComponent(code)}`).then(r => r.data),
  referralSetCode: (code) => client.put(`/referral/code`, { code }).then(r => r.data),
};
