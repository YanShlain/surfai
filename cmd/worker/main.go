package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"neon/internal/app"
	"neon/internal/infrastructure/memory"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	ctx := context.Background()
	application, err := app.BootstrapApp(ctx, app.DefaultWorkerOptions(memory.DefaultSeedConfig()))
	if err != nil {
		slog.Error("bootstrap failed", "error", err)
		os.Exit(1)
	}
	defer application.Close()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		if err := application.RunWorker(); err != nil {
			slog.Error("worker stopped", "error", err)
			os.Exit(1)
		}
	}()

	<-stop
}
