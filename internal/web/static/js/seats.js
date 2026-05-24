(function initSeatsPage() {
  const params = new URLSearchParams(window.location.search);
  const flightID = params.get("flight_id");

  const flightIdEl = document.getElementById("flight-id");
  const flightMetaEl = document.getElementById("flight-meta");
  const departedBanner = document.getElementById("departed-banner");
  const loadingEl = document.getElementById("loading");
  const errorEl = document.getElementById("error");
  const seatMapEl = document.getElementById("seat-map");
  const gridEl = document.getElementById("seat-grid");
  const refreshBtn = document.getElementById("refresh-btn");

  if (!flightID) {
    loadingEl.classList.add("hidden");
    showError(errorEl, "Missing flight_id. Go back and select a flight.");
    return;
  }

  flightIdEl.textContent = flightID;
  refreshBtn.addEventListener("click", () => loadSeatMap(flightID));

  loadFlightMeta(flightID);
  loadSeatMap(flightID);

  async function loadFlightMeta(id) {
    try {
      const data = await fetchJSON("/flights");
      const flight = (data.flights || []).find((f) => f.id === id);
      if (!flight) {
        return;
      }
      flightMetaEl.textContent = `Departs ${formatDateTime(flight.departure_at)} · ${flight.capacity} seats`;
      if (isDeparted(flight.departure_at)) {
        departedBanner.classList.remove("hidden");
      } else {
        departedBanner.classList.add("hidden");
      }
    } catch {
      flightMetaEl.textContent = "";
    }
  }

  async function loadSeatMap(id) {
    hideError(errorEl);
    loadingEl.classList.remove("hidden");
    seatMapEl.classList.add("hidden");

    try {
      const data = await fetchJSON(`/flights/${encodeURIComponent(id)}/seats`);
      loadingEl.classList.add("hidden");
      renderSeatGrid(gridEl, data.seats || []);
      seatMapEl.classList.remove("hidden");
    } catch (err) {
      loadingEl.classList.add("hidden");
      showError(errorEl, `Could not load seat map: ${err.message}`);
    }
  }
})();

function parseSeatID(seatID) {
  const match = /^(\d+)([A-Z]+)$/.exec(seatID);
  if (!match) {
    return null;
  }
  return { row: parseInt(match[1], 10), col: match[2] };
}

function renderSeatGrid(container, seats) {
  const parsed = seats.map((s) => ({ ...s, pos: parseSeatID(s.seat_id) })).filter((s) => s.pos);

  if (parsed.length === 0) {
    container.innerHTML = "<p>No seats to display.</p>";
    return;
  }

  const rows = [...new Set(parsed.map((s) => s.pos.row))].sort((a, b) => a - b);
  const cols = [...new Set(parsed.map((s) => s.pos.col))].sort();
  const seatByKey = new Map(parsed.map((s) => [`${s.pos.row}${s.pos.col}`, s]));

  const grid = document.createElement("div");
  grid.className = "seat-grid";
  grid.style.gridTemplateColumns = `2rem repeat(${cols.length}, 2rem)`;

  grid.appendChild(cell("corner", ""));

  cols.forEach((col) => {
    grid.appendChild(cell("col-label", col));
  });

  rows.forEach((row) => {
    grid.appendChild(cell("row-label", String(row)));
    cols.forEach((col) => {
      const seat = seatByKey.get(`${row}${col}`);
      if (seat) {
        grid.appendChild(seatCell(seat));
      } else {
        grid.appendChild(cell("corner", ""));
      }
    });
  });

  container.innerHTML = "";
  container.appendChild(grid);
}

function cell(className, text) {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = text;
  return el;
}

function seatCell(seat) {
  const el = document.createElement("div");
  const status = (seat.status || "AVAILABLE").toLowerCase();
  el.className = `seat-cell ${status}`;
  el.title = `${seat.seat_id} — ${seat.status}`;
  el.setAttribute("aria-label", `${seat.seat_id} ${seat.status}`);
  el.textContent = seat.seat_id.replace(/^\d+/, "");
  return el;
}
