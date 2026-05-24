(async function initFlightsPage() {
  const loadingEl = document.getElementById("loading");
  const errorEl = document.getElementById("error");
  const flightsEl = document.getElementById("flights");

  try {
    const data = await fetchJSON("/flights");
    loadingEl.classList.add("hidden");

    if (!data.flights || data.flights.length === 0) {
      showError(errorEl, "No flights available.");
      return;
    }

    flightsEl.innerHTML = data.flights
      .map(
        (f) => `
        <a class="flight-card" href="/seats?flight_id=${encodeURIComponent(f.id)}">
          <h2 class="flight-card-id">Flight ${escapeHTML(f.id)}</h2>
          <p class="flight-card-meta">Departs ${formatDateTime(f.departure_at)}</p>
          <p class="flight-card-meta">${f.capacity} seats</p>
        </a>`
      )
      .join("");

    flightsEl.classList.remove("hidden");
  } catch (err) {
    loadingEl.classList.add("hidden");
    showError(errorEl, `Could not load flights: ${err.message}`);
  }
})();

function escapeHTML(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
