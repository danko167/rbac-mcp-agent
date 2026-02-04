import axios from "axios";

let inMemoryToken: string | null = localStorage.getItem("token");

export function setApiToken(token: string | null) {
  inMemoryToken = token;
  if (token) localStorage.setItem("token", token);
  else localStorage.removeItem("token");
}

const api = axios.create({
  // Vite: define VITE_API_BASE_URL in .env.local
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});

// attach token
api.interceptors.request.use((config) => {
  const token = inMemoryToken;
  if (token) {
    config.headers = config.headers ?? {};
    // axios headers can be a special type; this is fine in practice
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

// handle 401 globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      setApiToken(null);
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;
