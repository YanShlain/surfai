const API_BASE = "/api/v1";

async function fetchJSON(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response.json();
}

function formatDateTime(iso) {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isDeparted(iso) {
  return new Date(iso).getTime() < Date.now();
}

function showError(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function hideError(el) {
  el.classList.add("hidden");
  el.textContent = "";
}
