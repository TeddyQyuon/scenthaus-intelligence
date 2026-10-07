import axios from "axios";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  withCredentials: true,
  timeout: 30000,
});
export const setCsrf = (token) => {
  api.defaults.headers.common["X-CSRF-Token"] = token;
};
export const message = (e) =>
  e.response?.data?.detail && typeof e.response.data.detail === "string"
    ? e.response.data.detail
    : "Something went wrong. Please try again.";
export const money = (n) =>
  new Intl.NumberFormat("en-SG", {
    style: "currency",
    currency: "SGD",
    maximumFractionDigits: 2,
  }).format(n || 0);
export function download(data, name, type = "application/json") {
  const url = URL.createObjectURL(
    new Blob(
      [typeof data === "string" ? data : JSON.stringify(data, null, 2)],
      { type },
    ),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
