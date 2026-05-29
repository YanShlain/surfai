package app

import (
	"context"
	"fmt"
	"log/slog"
	"os"

	"github.com/gin-gonic/gin"

	"neon/internal/api"
	"neon/internal/infrastructure/memory"
	"neon/internal/infrastructure/temporal"
)

// Options configures application bootstrap.
type Options struct {
	SeedConfig     memory.SeedConfig
	StartWorker    bool
	ReconcileHolds bool
}

// Application wires repositories, Temporal, worker, and HTTP routes.
type Application struct {
	Repos    *Repos
	Temporal *temporal.Runtime
	Orders   *temporal.OrderService
}

// BootstrapApp seeds inventory, connects Temporal, optionally starts worker, and reconciles holds.
func BootstrapApp(ctx context.Context, opts Options) (*Application, error) {
	if opts.SeedConfig.FlightIDs == nil {
		opts.SeedConfig = memory.DefaultSeedConfig()
	}

	repos, err := Bootstrap(opts.SeedConfig)
	if err != nil {
		return nil, err
	}

	if os.Getenv("TEMPORAL_AUTO_DEV") == "" {
		os.Setenv("TEMPORAL_AUTO_DEV", "1")
	}

	rt, err := temporal.Connect(ctx, temporal.ConnectOptions{})
	if err != nil {
		return nil, fmt.Errorf("connect temporal: %w", err)
	}

	app := &Application{
		Repos:    repos,
		Temporal: rt,
		Orders:   temporal.NewOrderService(rt.Client),
	}

	if opts.ReconcileHolds {
		if err := ReconcileHolds(ctx, rt.Client, repos.Seats); err != nil {
			slog.Warn("hold reconciliation failed", "error", err)
		}
	}

	if opts.StartWorker {
		w := rt.StartWorker(repos.Seats)
		rt.Worker = w
		if opts.runWorkerInline() {
			go func() {
				slog.Info("starting temporal worker", "task_queue", "booking-task-queue")
				if err := w.Run(nil); err != nil {
					slog.Error("worker stopped", "error", err)
				}
			}()
		}
	}

	if opts.StartWorker && os.Getenv("NEON_ROLE") == "api" && os.Getenv("TEMPORAL_AUTO_DEV") == "0" {
		slog.Warn("split deployment with in-memory seats: run a single API+worker process or use durable storage")
	}

	return app, nil
}

func (o Options) runWorkerInline() bool {
	return os.Getenv("NEON_ROLE") != "worker"
}

// RunWorker blocks until the Temporal worker stops. Call from cmd/worker after BootstrapApp.
func (a *Application) RunWorker() error {
	if a.Temporal == nil || a.Temporal.Worker == nil {
		return fmt.Errorf("worker not started")
	}
	slog.Info("worker running", "task_queue", "booking-task-queue")
	return a.Temporal.Worker.Run(nil)
}

// NewRouter builds the HTTP router.
func (a *Application) NewRouter() *gin.Engine {
	return api.NewRouter(a.Repos.Flights, a.Repos.Seats, a.Orders)
}

// Close releases runtime resources.
func (a *Application) Close() {
	if a.Temporal != nil {
		a.Temporal.Close()
	}
}

// DefaultAPIOptions returns bootstrap options for cmd/api (embedded worker + reconcile).
func DefaultAPIOptions(seed memory.SeedConfig) Options {
	os.Setenv("NEON_ROLE", "api")
	return Options{
		SeedConfig:     seed,
		StartWorker:    os.Getenv("EMBED_TEMPORAL_WORKER") != "0",
		ReconcileHolds: true,
	}
}

// DefaultWorkerOptions returns bootstrap options for cmd/worker.
func DefaultWorkerOptions(seed memory.SeedConfig) Options {
	os.Setenv("NEON_ROLE", "worker")
	return Options{
		SeedConfig:     seed,
		StartWorker:    true,
		ReconcileHolds: true,
	}
}
