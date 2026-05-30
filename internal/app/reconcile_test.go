package app_test

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"go.temporal.io/api/common/v1"
	"go.temporal.io/api/workflow/v1"
	"go.temporal.io/api/workflowservice/v1"
	temporalmocks "go.temporal.io/sdk/mocks"

	"neon/domain"
	"neon/internal/app"
	"neon/internal/infrastructure/memory"
	"neon/internal/workflow/booking"
)

// DATA-2: ReconcileInventory applies held seats from running workflows.
func TestU_DATA2_ReconcileInventoryAppliesHolds(t *testing.T) {
	ctx := context.Background()
	seats := seedTestSeats(t)

	orderID := "O-reconcile-1"
	flightID := memory.Flight1ID
	heldSeats := []string{"1A", "1B"}

	status := booking.StatusResponse{
		Status:      domain.OrderStatusSeatsHeld,
		FlightID:    flightID,
		HeldSeatIDs: heldSeats,
	}

	mv := temporalmocks.NewEncodedValue(t)
	mv.On("Get", mock.Anything).Run(func(args mock.Arguments) {
		data, err := json.Marshal(status)
		require.NoError(t, err)
		require.NoError(t, json.Unmarshal(data, args.Get(0)))
	}).Return(nil)

	mc := temporalmocks.NewClient(t)
	mc.On("ListWorkflow", mock.Anything, mock.MatchedBy(func(r *workflowservice.ListWorkflowExecutionsRequest) bool {
		return r.Query != ""
	})).Return(&workflowservice.ListWorkflowExecutionsResponse{
		Executions: []*workflow.WorkflowExecutionInfo{
			{Execution: &common.WorkflowExecution{WorkflowId: orderID, RunId: "run-1"}},
		},
	}, nil)
	mc.On("QueryWorkflow", mock.Anything, orderID, "", booking.QueryGetStatus).
		Return(mv, nil)

	require.NoError(t, app.ReconcileInventory(ctx, mc, seats))

	list, err := seats.ListByFlight(ctx, flightID)
	require.NoError(t, err)
	held := map[string]bool{}
	for _, s := range list {
		if s.Status == domain.SeatStatusHeld && s.OrderID == orderID {
			held[s.SeatID] = true
		}
	}
	for _, id := range heldSeats {
		require.True(t, held[id], "seat %s should be HELD by %s after reconcile", id, orderID)
	}
}

// ReconcileInventory with empty running-workflow list returns nil and touches no seats.
func TestU_DATA2b_ReconcileInventoryEmptyList(t *testing.T) {
	ctx := context.Background()
	seats := seedTestSeats(t)

	mc := temporalmocks.NewClient(t)
	mc.On("ListWorkflow", mock.Anything, mock.Anything).
		Return(&workflowservice.ListWorkflowExecutionsResponse{}, nil)

	require.NoError(t, app.ReconcileInventory(ctx, mc, seats))
}

func seedTestSeats(t *testing.T) domain.SeatRepository {
	t.Helper()
	flights := memory.NewFlightRepository()
	seats := memory.NewSeatRepository()
	require.NoError(t, memory.Seed(flights, seats, memory.DefaultSeedConfig()))
	return seats
}
