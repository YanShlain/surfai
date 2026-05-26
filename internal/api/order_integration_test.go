package api_test

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"neon/internal/app"
	"neon/internal/infrastructure/memory"
)

func newTestApp(t *testing.T) *httptest.Server {
	t.Helper()
	t.Setenv("TEMPORAL_AUTO_DEV", "1")
	if os.Getenv("HOLD_DURATION") == "" {
		t.Setenv("HOLD_DURATION", "30s")
	}

	application, err := app.BootstrapApp(context.Background(), memory.DefaultSeedConfig())
	if err != nil {
		t.Fatalf("bootstrap app: %v", err)
	}
	t.Cleanup(application.Close)

	srv := httptest.NewServer(application.NewRouter())
	t.Cleanup(srv.Close)
	return srv
}

func newTestServer(t *testing.T) (*httptest.Server, *memory.SeatRepository) {
	t.Helper()
	t.Setenv("TEMPORAL_AUTO_DEV", "1")
	if os.Getenv("HOLD_DURATION") == "" {
		t.Setenv("HOLD_DURATION", "30s")
	}

	application, err := app.BootstrapApp(context.Background(), memory.DefaultSeedConfig())
	if err != nil {
		t.Fatalf("bootstrap app: %v", err)
	}
	t.Cleanup(application.Close)

	seatRepo, ok := application.Repos.Seats.(*memory.SeatRepository)
	if !ok {
		t.Fatal("expected *memory.SeatRepository")
	}
	srv := httptest.NewServer(application.NewRouter())
	t.Cleanup(srv.Close)
	return srv, seatRepo
}

func postJSON(t *testing.T, url string, body any) *http.Response {
	t.Helper()
	data, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	resp, err := http.Post(url, "application/json", bytes.NewReader(data))
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	return resp
}

func patchJSON(t *testing.T, url string, body any) *http.Response {
	t.Helper()
	data, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	req, err := http.NewRequest(http.MethodPatch, url, bytes.NewReader(data))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("PATCH %s: %v", url, err)
	}
	return resp
}

type orderBody struct {
	OrderID               string   `json:"order_id"`
	FlightID              string   `json:"flight_id"`
	Status                string   `json:"status"`
	HeldSeatIDs           []string `json:"held_seat_ids"`
	TimerRemainingSeconds int      `json:"timer_remaining_seconds"`
}

func decodeOrder(t *testing.T, resp *http.Response) orderBody {
	t.Helper()
	defer resp.Body.Close()
	var body orderBody
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode order: %v", err)
	}
	return body
}

func createOrder(t *testing.T, srv *httptest.Server, flightID string) orderBody {
	t.Helper()
	resp := postJSON(t, srv.URL+"/api/v1/orders", map[string]string{"flight_id": flightID})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create order status = %d", resp.StatusCode)
	}
	return decodeOrder(t, resp)
}

// I-B1: S-2 Timer refresh — timer_remaining_seconds ≈900 after seat change
func TestI_B1_TimerRefreshAfterSeatChange(t *testing.T) {
	t.Setenv("HOLD_DURATION", "15m")
	srv := newTestApp(t)

	order := createOrder(t, srv, "101")
	resp := patchJSON(t, srv.URL+"/api/v1/orders/"+order.OrderID+"/seats", map[string]any{
		"seat_ids": []string{"1A"},
	})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("patch seats status = %d", resp.StatusCode)
	}
	body := decodeOrder(t, resp)
	if body.Status != "SEATS_HELD" {
		t.Fatalf("status = %q, want SEATS_HELD", body.Status)
	}
	if body.TimerRemainingSeconds < 895 || body.TimerRemainingSeconds > 900 {
		t.Fatalf("timer_remaining_seconds = %d, want ~900", body.TimerRemainingSeconds)
	}
}

// I-B2: S-5 Multi-flight — Isolated holds on 101 vs 102
func TestI_B2_MultiFlightHoldIsolation(t *testing.T) {
	srv := newTestApp(t)

	o1 := createOrder(t, srv, "101")
	resp1 := patchJSON(t, srv.URL+"/api/v1/orders/"+o1.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("order1 patch status = %d", resp1.StatusCode)
	}

	o2 := createOrder(t, srv, "102")
	resp2 := patchJSON(t, srv.URL+"/api/v1/orders/"+o2.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp2.StatusCode != http.StatusOK {
		t.Fatalf("order2 patch status = %d", resp2.StatusCode)
	}

	seatsResp, err := http.Get(srv.URL + "/api/v1/flights/102/seats")
	if err != nil {
		t.Fatalf("get seats: %v", err)
	}
	defer seatsResp.Body.Close()
	raw, _ := io.ReadAll(seatsResp.Body)
	if !strings.Contains(string(raw), `"seat_id":"1A"`) && !strings.Contains(string(raw), `"seat_id": "1A"`) {
		t.Fatalf("expected seat 1A on flight 102")
	}
}

// I-B3: Cancel — CANCELLED; seats released
func TestI_B3_CancelOrderReleasesSeats(t *testing.T) {
	srv := newTestApp(t)

	order := createOrder(t, srv, "101")
	resp := patchJSON(t, srv.URL+"/api/v1/orders/"+order.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("patch status = %d", resp.StatusCode)
	}
	resp.Body.Close()

	cancelResp, err := http.Post(srv.URL+"/api/v1/orders/"+order.OrderID+"/cancel", "application/json", nil)
	if err != nil {
		t.Fatalf("cancel: %v", err)
	}
	body := decodeOrder(t, cancelResp)
	if body.Status != "CANCELLED" {
		t.Fatalf("status = %q, want CANCELLED", body.Status)
	}

	seatsResp, err := http.Get(srv.URL + "/api/v1/flights/101/seats")
	if err != nil {
		t.Fatalf("get seats: %v", err)
	}
	defer seatsResp.Body.Close()
	var seatMap struct {
		Seats []struct {
			SeatID string `json:"seat_id"`
			Status string `json:"status"`
		} `json:"seats"`
	}
	if err := json.NewDecoder(seatsResp.Body).Decode(&seatMap); err != nil {
		t.Fatalf("decode seats: %v", err)
	}
	for _, seat := range seatMap.Seats {
		if seat.SeatID == "1A" && seat.Status != "AVAILABLE" {
			t.Fatalf("1A status = %q, want AVAILABLE", seat.Status)
		}
	}
}

// I-B4: Expiry — EXPIRED after hold duration
func TestI_B4_OrderExpiresAfterHoldDuration(t *testing.T) {
	t.Setenv("HOLD_DURATION", "2s")
	srv := newTestApp(t)

	order := createOrder(t, srv, "101")
	resp := patchJSON(t, srv.URL+"/api/v1/orders/"+order.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("patch status = %d", resp.StatusCode)
	}
	resp.Body.Close()

	time.Sleep(3 * time.Second)

	getResp, err := http.Get(srv.URL + "/api/v1/orders/" + order.OrderID)
	if err != nil {
		t.Fatalf("get order: %v", err)
	}
	body := decodeOrder(t, getResp)
	if body.Status != "EXPIRED" {
		t.Fatalf("status = %q, want EXPIRED", body.Status)
	}
}

// I-B5: Hold conflict — 409 for second holder
func TestI_B5_HoldConflictReturns409(t *testing.T) {
	srv := newTestApp(t)

	o1 := createOrder(t, srv, "101")
	resp1 := patchJSON(t, srv.URL+"/api/v1/orders/"+o1.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("order1 patch status = %d", resp1.StatusCode)
	}
	resp1.Body.Close()

	o2 := createOrder(t, srv, "101")
	resp2 := patchJSON(t, srv.URL+"/api/v1/orders/"+o2.OrderID+"/seats", map[string]any{"seat_ids": []string{"1A"}})
	if resp2.StatusCode != http.StatusConflict {
		t.Fatalf("order2 patch status = %d, want 409", resp2.StatusCode)
	}
	resp2.Body.Close()
}
