package memory

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"

	"neon/domain"
)

var (
	ErrFlightNotFound = domain.ErrFlightNotFound
	ErrHoldConflict   = domain.ErrHoldConflict
	ErrInvalidConfirm = domain.ErrInvalidConfirm
	ErrSeatNotFound   = errors.New("seat not found")
)

type flightInventory struct {
	mu    sync.RWMutex
	seats map[string]domain.Seat
}

// SeatRepository is an in-memory SeatRepository with per-flight locking.
type SeatRepository struct {
	mu      sync.RWMutex
	flights map[string]*flightInventory
}

// NewSeatRepository creates an empty seat repository.
func NewSeatRepository() *SeatRepository {
	return &SeatRepository{
		flights: make(map[string]*flightInventory),
	}
}

func (r *SeatRepository) initFlight(flightID string, rows, columns int) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.flights[flightID]; exists {
		return fmt.Errorf("flight %q already initialized", flightID)
	}

	seats := make(map[string]domain.Seat, rows*columns)
	for _, seatID := range GenerateSeatIDs(rows, columns) {
		seats[seatID] = domain.Seat{
			FlightID: flightID,
			SeatID:   seatID,
			Status:   domain.SeatStatusAvailable,
		}
	}
	r.flights[flightID] = &flightInventory{seats: seats}
	return nil
}

func (r *SeatRepository) flightInv(flightID string) (*flightInventory, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	inv, ok := r.flights[flightID]
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrFlightNotFound, flightID)
	}
	return inv, nil
}

// ListByFlight returns all seats for a flight sorted by seat ID.
func (r *SeatRepository) ListByFlight(_ context.Context, flightID string) ([]domain.Seat, error) {
	inv, err := r.flightInv(flightID)
	if err != nil {
		return nil, err
	}

	inv.mu.RLock()
	defer inv.mu.RUnlock()

	out := make([]domain.Seat, 0, len(inv.seats))
	for _, seat := range inv.seats {
		out = append(out, seat)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].SeatID < out[j].SeatID
	})
	return out, nil
}

// TryHold marks seats as HELD for the given order when all are available.
func (r *SeatRepository) TryHold(_ context.Context, flightID string, seatIDs []string, orderID string) error {
	inv, err := r.flightInv(flightID)
	if err != nil {
		return err
	}

	inv.mu.Lock()
	defer inv.mu.Unlock()

	if err := validateAvailable(inv.seats, seatIDs); err != nil {
		return err
	}
	for _, seatID := range seatIDs {
		seat := inv.seats[seatID]
		seat.Status = domain.SeatStatusHeld
		seat.OrderID = orderID
		inv.seats[seatID] = seat
	}
	return nil
}

// SwapHold atomically releases held seats and holds new ones for an order.
func (r *SeatRepository) SwapHold(_ context.Context, flightID, orderID string, releaseIDs, holdIDs []string) error {
	inv, err := r.flightInv(flightID)
	if err != nil {
		return err
	}

	inv.mu.Lock()
	defer inv.mu.Unlock()

	if err := validateRelease(inv.seats, releaseIDs, orderID); err != nil {
		return err
	}
	if err := validateHoldAfterRelease(inv.seats, releaseIDs, holdIDs, orderID); err != nil {
		return err
	}

	for _, seatID := range releaseIDs {
		seat := inv.seats[seatID]
		seat.Status = domain.SeatStatusAvailable
		seat.OrderID = ""
		inv.seats[seatID] = seat
	}
	for _, seatID := range holdIDs {
		seat := inv.seats[seatID]
		seat.Status = domain.SeatStatusHeld
		seat.OrderID = orderID
		inv.seats[seatID] = seat
	}
	return nil
}

// ApplyHold idempotently applies holds from workflow state during reconciliation.
func (r *SeatRepository) ApplyHold(_ context.Context, flightID, orderID string, seatIDs []string) error {
	if len(seatIDs) == 0 {
		return nil
	}
	inv, err := r.flightInv(flightID)
	if err != nil {
		return err
	}

	inv.mu.Lock()
	defer inv.mu.Unlock()

	for _, seatID := range seatIDs {
		seat, found := inv.seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		switch seat.Status {
		case domain.SeatStatusAvailable:
			seat.Status = domain.SeatStatusHeld
			seat.OrderID = orderID
			inv.seats[seatID] = seat
		case domain.SeatStatusHeld:
			if seat.OrderID != orderID {
				return ErrHoldConflict
			}
		case domain.SeatStatusBooked:
			if seat.OrderID != orderID {
				return ErrHoldConflict
			}
		}
	}
	return nil
}

// Release returns held seats to AVAILABLE for the given order.
func (r *SeatRepository) Release(_ context.Context, flightID string, seatIDs []string, orderID string) error {
	if len(seatIDs) == 0 {
		return nil
	}
	inv, err := r.flightInv(flightID)
	if err != nil {
		return err
	}

	inv.mu.Lock()
	defer inv.mu.Unlock()

	for _, seatID := range seatIDs {
		seat, found := inv.seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		if seat.Status == domain.SeatStatusAvailable {
			continue
		}
		if seat.Status != domain.SeatStatusHeld || seat.OrderID != orderID {
			return domain.ErrInvalidRelease
		}
		seat.Status = domain.SeatStatusAvailable
		seat.OrderID = ""
		inv.seats[seatID] = seat
	}
	return nil
}

// Confirm transitions held seats to BOOKED for the given order.
func (r *SeatRepository) Confirm(_ context.Context, flightID string, seatIDs []string, orderID string) error {
	if len(seatIDs) == 0 {
		return nil
	}
	inv, err := r.flightInv(flightID)
	if err != nil {
		return err
	}

	inv.mu.Lock()
	defer inv.mu.Unlock()

	for _, seatID := range seatIDs {
		seat, found := inv.seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		if seat.Status != domain.SeatStatusHeld || seat.OrderID != orderID {
			return ErrInvalidConfirm
		}
		seat.Status = domain.SeatStatusBooked
		inv.seats[seatID] = seat
	}
	return nil
}

func validateAvailable(seats map[string]domain.Seat, seatIDs []string) error {
	for _, seatID := range seatIDs {
		seat, found := seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		if seat.Status != domain.SeatStatusAvailable {
			return ErrHoldConflict
		}
	}
	return nil
}

func validateHoldAfterRelease(seats map[string]domain.Seat, releaseIDs, holdIDs []string, orderID string) error {
	releasing := make(map[string]struct{}, len(releaseIDs))
	for _, seatID := range releaseIDs {
		releasing[seatID] = struct{}{}
	}
	for _, seatID := range holdIDs {
		seat, found := seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		if _, ok := releasing[seatID]; ok {
			if seat.Status == domain.SeatStatusHeld && seat.OrderID == orderID {
				continue
			}
		}
		if seat.Status != domain.SeatStatusAvailable {
			return ErrHoldConflict
		}
	}
	return nil
}

func validateRelease(seats map[string]domain.Seat, seatIDs []string, orderID string) error {
	for _, seatID := range seatIDs {
		seat, found := seats[seatID]
		if !found {
			return fmt.Errorf("%w: %s", ErrSeatNotFound, seatID)
		}
		if seat.Status != domain.SeatStatusHeld || seat.OrderID != orderID {
			return domain.ErrInvalidRelease
		}
	}
	return nil
}
