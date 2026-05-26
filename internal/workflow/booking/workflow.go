package booking

import (
	"errors"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"

	"neon/domain"
	"neon/internal/infrastructure/memory"
)

const activityTimeout = 30 * time.Second

func activityCtx(ctx workflow.Context) workflow.Context {
	return workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: activityTimeout,
	})
}

type workflowState struct {
	OrderID       string
	FlightID      string
	HoldDuration  time.Duration
	Status        domain.OrderStatus
	HeldSeatIDs   []string
	TimerDeadline time.Time
	LastError     string
}

// BookingWorkflow orchestrates seat holds and the hold timer (MVP-B scope).
func BookingWorkflow(ctx workflow.Context, input WorkflowInput) error {
	// --- Init state ---
	state := workflowState{
		OrderID:      input.OrderID,
		FlightID:     input.FlightID,
		HoldDuration: input.HoldDuration,
		Status:       domain.OrderStatusCreated,
	}
	if state.HoldDuration <= 0 {
		state.HoldDuration = 15 * time.Minute
	}

	actCtx := activityCtx(ctx)
	resetCh := workflow.NewBufferedChannel(ctx, 1)

	notifyTimerReset := func() {
		resetCh.SendAsync(true)
	}

	if err := workflow.SetQueryHandler(ctx, QueryGetStatus, func() (StatusResponse, error) {
		return state.toResponse(workflow.Now(ctx)), nil
	}); err != nil {
		return err
	}

	if err := workflow.SetUpdateHandler(ctx, UpdateUpdateSeats, func(updateCtx workflow.Context, req UpdateSeatsRequest) (StatusResponse, error) {
		if state.Status.IsTerminal() {
			return StatusResponse{}, temporal.NewApplicationError("order terminal", "terminal_order")
		}
		if err := applySeatUpdate(activityCtx(updateCtx), &state, req.SeatIDs); err != nil {
			return StatusResponse{}, err
		}
		notifyTimerReset()
		return state.toResponse(workflow.Now(ctx)), nil
	}); err != nil {
		return err
	}

	if err := workflow.SetUpdateHandler(ctx, UpdateCancelOrder, func(updateCtx workflow.Context) (StatusResponse, error) {
		if state.Status.IsTerminal() {
			return state.toResponse(workflow.Now(ctx)), nil
		}
		if err := releaseHeldSeats(activityCtx(updateCtx), &state); err != nil {
			return StatusResponse{}, err
		}
		state.Status = domain.OrderStatusCancelled
		state.TimerDeadline = time.Time{}
		notifyTimerReset()
		return state.toResponse(workflow.Now(ctx)), nil
	}); err != nil {
		return err
	}

	// --- Selector loop until terminal ---
	for !state.Status.IsTerminal() {
		if state.TimerDeadline.IsZero() {
			_ = workflow.Await(ctx, func() bool {
				return state.Status.IsTerminal() || !state.TimerDeadline.IsZero()
			})
			continue
		}

		deadline := state.TimerDeadline
		timerCtx, timerCancel := workflow.WithCancel(ctx)
		remaining := deadline.Sub(workflow.Now(ctx))
		if remaining <= 0 {
			timerCancel()
			if err := expireOrder(actCtx, &state); err != nil {
				return err
			}
			continue
		}

		timerFuture := workflow.NewTimer(timerCtx, remaining)
		expired := false
		reset := false

		selector := workflow.NewSelector(ctx)
		selector.AddFuture(timerFuture, func(f workflow.Future) {
			_ = f.Get(timerCtx, nil)
			if state.TimerDeadline.Equal(deadline) && !state.Status.IsTerminal() {
				expired = true
			}
		})
		selector.AddReceive(resetCh, func(c workflow.ReceiveChannel, more bool) {
			var ignored bool
			c.Receive(ctx, &ignored)
			reset = true
		})
		selector.Select(ctx)
		timerCancel()

		if reset {
			continue
		}
		if expired {
			if err := expireOrder(actCtx, &state); err != nil {
				return err
			}
		}
	}
	return nil
}

func expireOrder(ctx workflow.Context, state *workflowState) error {
	if err := releaseHeldSeats(ctx, state); err != nil {
		return err
	}
	state.Status = domain.OrderStatusExpired
	state.TimerDeadline = time.Time{}
	return nil
}

func applySeatUpdate(ctx workflow.Context, state *workflowState, seatIDs []string) error {
	state.LastError = ""

	if len(state.HeldSeatIDs) > 0 {
		if err := workflow.ExecuteActivity(ctx, (*Activities).ReleaseSeats, SeatMutationInput{
			FlightID: state.FlightID,
			SeatIDs:  cloneStrings(state.HeldSeatIDs),
			OrderID:  state.OrderID,
		}).Get(ctx, nil); err != nil {
			return err
		}
	}

	if len(seatIDs) > 0 {
		err := workflow.ExecuteActivity(ctx, (*Activities).HoldSeats, SeatMutationInput{
			FlightID: state.FlightID,
			SeatIDs:  seatIDs,
			OrderID:  state.OrderID,
		}).Get(ctx, nil)
		if err != nil {
			if errors.Is(err, memory.ErrHoldConflict) {
				return temporal.NewNonRetryableApplicationError("seat hold conflict", "hold_conflict", err)
			}
			return err
		}
	}

	state.HeldSeatIDs = cloneStrings(seatIDs)
	state.Status = domain.OrderStatusSeatsHeld
	state.TimerDeadline = workflow.Now(ctx).Add(state.HoldDuration)
	return nil
}

func releaseHeldSeats(ctx workflow.Context, state *workflowState) error {
	if len(state.HeldSeatIDs) == 0 {
		return nil
	}
	err := workflow.ExecuteActivity(ctx, (*Activities).ReleaseSeats, SeatMutationInput{
		FlightID: state.FlightID,
		SeatIDs:  cloneStrings(state.HeldSeatIDs),
		OrderID:  state.OrderID,
	}).Get(ctx, nil)
	if err != nil {
		return err
	}
	state.HeldSeatIDs = nil
	return nil
}

func (s workflowState) toResponse(now time.Time) StatusResponse {
	return StatusResponse{
		OrderID:               s.OrderID,
		FlightID:              s.FlightID,
		Status:                s.Status,
		HeldSeatIDs:           cloneStrings(s.HeldSeatIDs),
		TimerRemainingSeconds: timerRemaining(s.TimerDeadline, now),
		LastError:             s.LastError,
	}
}
