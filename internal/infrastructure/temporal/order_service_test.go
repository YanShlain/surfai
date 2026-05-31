package temporal

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/temporal"

	"neon/domain"
	"neon/internal/workflow/booking"
)

func TestMapTemporalError_applicationTypes(t *testing.T) {
	t.Parallel()
	cases := []struct {
		typ    string
		want   error
		notWant error
	}{
		{"hold_conflict", ErrHoldConflict, nil},
		{"terminal_order", ErrTerminalOrder, nil},
		{"payment_in_progress", ErrPaymentInProgress, nil},
		{"payment_not_allowed", ErrPaymentNotAllowed, nil},
		{"invalid_payment_code", ErrInvalidPaymentCode, nil},
		{"unknown_type", nil, ErrHoldConflict},
	}
	for _, tc := range cases {
		t.Run(tc.typ, func(t *testing.T) {
			err := temporal.NewApplicationError("msg", tc.typ)
			got := mapTemporalError(err)
			if tc.want != nil {
				require.ErrorIs(t, got, tc.want)
				return
			}
			require.NotErrorIs(t, got, tc.notWant)
			var appErr *temporal.ApplicationError
			require.True(t, errors.As(got, &appErr))
		})
	}
}

func TestMapPaymentResultError_lastErrorStrings(t *testing.T) {
	t.Parallel()
	cases := []struct {
		last    string
		wantErr error
	}{
		{"payment validation failed", nil},
		{"invalid payment code format", ErrInvalidPaymentCode},
		{"payment not allowed", ErrPaymentNotAllowed},
		{"", nil},
		{"other", nil},
	}
	for _, tc := range cases {
		t.Run(tc.last, func(t *testing.T) {
			got := mapPaymentResultError(booking.StatusResponse{
				Status:    domain.OrderStatusSeatsHeld,
				LastError: tc.last,
			})
			if tc.wantErr == nil {
				require.NoError(t, got)
				return
			}
			require.ErrorIs(t, got, tc.wantErr)
		})
	}
}
