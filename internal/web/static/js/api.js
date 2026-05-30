const API_BASE = "/api/v1";
const ORDER_STORAGE_KEY = "neon_order_id";
const ORDER_POLL_INTERVAL_MS = 5000;

async function fetchJSON(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body.error) {
        message = body.error;
      }
    } catch {
      // ignore parse errors
    }
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function postJSON(path, body) {
  return fetchJSON(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function patchJSON(path, body) {
  return fetchJSON(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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

function formatOrderDisplayID(orderID) {
  if (!orderID) {
    return "—";
  }
  const compact = String(orderID).replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
  return compact.slice(0, 8).padEnd(8, "0");
}

function formatTimer(totalSeconds) {
  const seconds = Math.max(0, totalSeconds);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
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

function getStoredOrderID() {
  return localStorage.getItem(ORDER_STORAGE_KEY);
}

function setStoredOrderID(orderID) {
  if (orderID) {
    localStorage.setItem(ORDER_STORAGE_KEY, orderID);
  } else {
    localStorage.removeItem(ORDER_STORAGE_KEY);
  }
}

function isTerminalStatus(status) {
  return status === "CONFIRMED" || status === "EXPIRED" || status === "CANCELLED" || status === "PAYMENT_FAILED";
}

function orderSeatsSignature(status, heldSeatIDs) {
  const seats = heldSeatIDs || [];
  return `${status}|${[...seats].sort().join(",")}`;
}

/** Hold timer runs only after at least one seat is held (not in bare CREATED). */
function shouldShowHoldTimer(order) {
  if (!order || isTerminalStatus(order.status)) {
    return false;
  }
  const heldCount = (order.held_seat_ids || []).length;
  if (order.status === "CREATED" && heldCount === 0) {
    return false;
  }
  return heldCount > 0 || order.status === "SEATS_HELD" || order.status === "AWAITING_PAYMENT";
}

function effectiveTimerSeconds(order) {
  if (!shouldShowHoldTimer(order)) {
    return 0;
  }
  return Math.max(0, order.timer_remaining_seconds || 0);
}

function updateTimerDisplay(el, seconds, show) {
  if (!show || seconds <= 0) {
    el.textContent = "—";
    return;
  }
  el.textContent = formatTimer(seconds);
}

/** Align local countdown with server; force=true after seat change or explicit refresh. */
function reconcileTimerSeconds(localSeconds, serverSeconds, { force = false } = {}) {
  const server = Math.max(0, serverSeconds || 0);
  if (force || localSeconds <= 0) {
    return server;
  }
  // Trust server when it falls behind (expiry / drift). Never snap forward on poll.
  if (server < localSeconds - 2) {
    return server;
  }
  return localSeconds;
}

function escapeHTML(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
