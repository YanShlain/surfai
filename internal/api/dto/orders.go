package dto

// CreateOrderRequest starts a booking for a flight.
type CreateOrderRequest struct {
	FlightID string `json:"flight_id" binding:"required"`
}

// UpdateSeatsRequest changes held seats on an order.
type UpdateSeatsRequest struct {
	SeatIDs []string `json:"seat_ids" binding:"required"`
}

// OrderResponse is returned by order endpoints.
type OrderResponse struct {
	OrderID               string   `json:"order_id"`
	FlightID              string   `json:"flight_id"`
	Status                string   `json:"status"`
	HeldSeatIDs           []string `json:"held_seat_ids"`
	TimerRemainingSeconds int      `json:"timer_remaining_seconds"`
}
