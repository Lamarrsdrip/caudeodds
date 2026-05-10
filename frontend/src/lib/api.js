import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

export const api = {
  generate: (force = false) => client.post(`/picks/generate?force=${force}`).then(r => r.data),
  today: () => client.get("/picks/today").then(r => r.data),
  history: (params = {}) => client.get("/picks/history", { params }).then(r => r.data),
  settle: (id, result) => client.post(`/picks/${id}/settle`, { result }).then(r => r.data),
  parlay: () => client.get("/picks/parlay").then(r => r.data),
  rejected: (params = {}) => client.get("/analytics/rejected", { params }).then(r => r.data),
  sharp: () => client.get("/analytics/sharp").then(r => r.data),
  roi: () => client.get("/analytics/roi").then(r => r.data),
  getConfig: () => client.get("/config").then(r => r.data),
  saveConfig: (s) => client.post("/config", s).then(r => r.data),
};
