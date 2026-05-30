package app

import (
	"errors"
	"fmt"
	"net"
	"strings"
	"syscall"
)

// AcquireListen binds addr exclusively. Only one process can hold a given TCP port.
func AcquireListen(addr string) (net.Listener, error) {
	return net.Listen("tcp", addr)
}

// ListenError maps bind failures to a user-facing message.
func ListenError(addr string, err error) error {
	if err == nil {
		return nil
	}
	if isAddrInUse(err) {
		return fmt.Errorf(
			"Neon API already running on %s. Stop the existing process or set API_ADDR to another port. "+
				"On Windows: netstat -ano | findstr \"%s\" then Stop-Process -Id <PID> -Force",
			addr, portForHint(addr),
		)
	}
	return fmt.Errorf("cannot listen on %s: %w", addr, err)
}

func isAddrInUse(err error) bool {
	if errors.Is(err, syscall.EADDRINUSE) {
		return true
	}
	var opErr *net.OpError
	if errors.As(err, &opErr) && opErr.Err != nil {
		return isAddrInUse(opErr.Err)
	}
	var errno syscall.Errno
	if errors.As(err, &errno) && errno == syscall.EADDRINUSE {
		return true
	}
	msg := err.Error()
	return strings.Contains(msg, "address already in use") ||
		strings.Contains(msg, "Only one usage of each socket address")
}

func portForHint(addr string) string {
	_, port, err := net.SplitHostPort(addr)
	if err != nil {
		return addr
	}
	return ":" + port
}
