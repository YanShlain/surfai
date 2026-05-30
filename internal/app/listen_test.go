package app_test

import (
	"errors"
	"net"
	"strings"
	"syscall"
	"testing"

	"github.com/stretchr/testify/require"

	"neon/internal/app"
)

func TestListenError_EADDRINUSE(t *testing.T) {
	err := app.ListenError(":8080", syscall.EADDRINUSE)
	require.Error(t, err)
	require.Contains(t, err.Error(), "Neon API already running")
	require.Contains(t, err.Error(), ":8080")
	require.Contains(t, err.Error(), "API_ADDR")
}

func TestListenError_OtherError(t *testing.T) {
	inner := errors.New("permission denied")
	err := app.ListenError(":8080", inner)
	require.Error(t, err)
	require.Contains(t, err.Error(), "cannot listen on :8080")
	require.ErrorIs(t, err, inner)
}

func TestAcquireListen_ConflictOnSamePort(t *testing.T) {
	ln1, err := app.AcquireListen("127.0.0.1:0")
	require.NoError(t, err)
	t.Cleanup(func() { _ = ln1.Close() })

	addr := ln1.Addr().String()
	ln2, err := app.AcquireListen(addr)
	require.Error(t, err)
	require.True(t, strings.Contains(err.Error(), "bind") || strings.Contains(err.Error(), "address"))
	if ln2 != nil {
		_ = ln2.Close()
	}
}

func TestAcquireListen_BindsEphemeralPort(t *testing.T) {
	ln, err := app.AcquireListen("127.0.0.1:0")
	require.NoError(t, err)
	defer ln.Close()

	_, port, err := net.SplitHostPort(ln.Addr().String())
	require.NoError(t, err)
	require.NotEmpty(t, port)
}
