package handler

import (
	"errors"
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"

	"neon/domain"
	"neon/internal/api/dto"
	"neon/internal/infrastructure/temporal"
	"neon/internal/workflow/booking"
)

// OrderHandler serves booking order endpoints.
type OrderHandler struct {
	orders *temporal.OrderService
}

// NewOrderHandler creates an OrderHandler.
func NewOrderHandler(orders *temporal.OrderService) *OrderHandler {
	return &OrderHandler{orders: orders}
}

// CreateOrder handles POST /api/v1/orders.
func (h *OrderHandler) CreateOrder(c *gin.Context) {
	ctx := c.Request.Context()
	slog.Info("inbound request", "method", c.Request.Method, "path", c.Request.URL.Path)

	var req dto.CreateOrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body"})
		return
	}

	status, err := h.orders.CreateOrder(ctx, req.FlightID)
	if err != nil {
		slog.Error("create order failed", "flight_id", req.FlightID, "error", err, "exc_info", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}
	c.JSON(http.StatusCreated, toOrderResponse(status))
}

// UpdateSeats handles PATCH /api/v1/orders/:order_id/seats.
func (h *OrderHandler) UpdateSeats(c *gin.Context) {
	ctx := c.Request.Context()
	orderID := c.Param("order_id")
	slog.Info("inbound request", "method", c.Request.Method, "path", c.Request.URL.Path, "order_id", orderID)

	var req dto.UpdateSeatsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body"})
		return
	}

	status, err := h.orders.UpdateSeats(ctx, orderID, req.SeatIDs)
	if err != nil {
		writeOrderError(c, orderID, err)
		return
	}
	c.JSON(http.StatusOK, toOrderResponse(status))
}

// CancelOrder handles POST /api/v1/orders/:order_id/cancel.
func (h *OrderHandler) CancelOrder(c *gin.Context) {
	ctx := c.Request.Context()
	orderID := c.Param("order_id")
	slog.Info("inbound request", "method", c.Request.Method, "path", c.Request.URL.Path, "order_id", orderID)

	status, err := h.orders.CancelOrder(ctx, orderID)
	if err != nil {
		writeOrderError(c, orderID, err)
		return
	}
	c.JSON(http.StatusOK, toOrderResponse(status))
}

// GetOrder handles GET /api/v1/orders/:order_id.
func (h *OrderHandler) GetOrder(c *gin.Context) {
	ctx := c.Request.Context()
	orderID := c.Param("order_id")
	slog.Info("inbound request", "method", c.Request.Method, "path", c.Request.URL.Path, "order_id", orderID)

	status, err := h.orders.GetStatus(ctx, orderID)
	if err != nil {
		writeOrderError(c, orderID, err)
		return
	}
	c.JSON(http.StatusOK, toOrderResponse(status))
}

func toOrderResponse(status booking.StatusResponse) dto.OrderResponse {
	return dto.OrderResponse{
		OrderID:               status.OrderID,
		FlightID:              status.FlightID,
		Status:                string(status.Status),
		HeldSeatIDs:           status.HeldSeatIDs,
		TimerRemainingSeconds: status.TimerRemainingSeconds,
	}
}

func writeOrderError(c *gin.Context, orderID string, err error) {
	slog.Error("order request failed", "order_id", orderID, "error", err, "exc_info", err)
	switch {
	case errors.Is(err, temporal.ErrOrderNotFound):
		c.JSON(http.StatusNotFound, gin.H{"error": "order not found"})
	case errors.Is(err, temporal.ErrHoldConflict):
		c.JSON(http.StatusConflict, gin.H{"error": "seat hold conflict"})
	case errors.Is(err, temporal.ErrTerminalOrder):
		c.JSON(http.StatusGone, gin.H{"error": "order is terminal"})
	default:
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
	}
}

// IsTerminalStatus reports whether an order status cannot be modified.
func IsTerminalStatus(status string) bool {
	return domain.OrderStatus(status).IsTerminal()
}
