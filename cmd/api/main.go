package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"neon/internal/app"
	"neon/internal/infrastructure/memory"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))

	addr := envOrDefault("API_ADDR", ":8080")
	ln, err := app.AcquireListen(addr)
	if err != nil {
		slog.Error("cannot start api server", "addr", addr, "error", app.ListenError(addr, err))
		os.Exit(1)
	}

	ctx := context.Background()
	application, err := app.BootstrapApp(ctx, app.DefaultAPIOptions(memory.DefaultSeedConfig()))
	if err != nil {
		slog.Error("bootstrap failed", "error", err)
		_ = ln.Close()
		os.Exit(1)
	}
	defer application.Close()

	router := application.NewRouter()
	srv := &http.Server{Handler: router}

	go func() {
		slog.Info("starting api server", "addr", addr)
		if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
			slog.Error("server stopped", "error", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	_ = srv.Shutdown(context.Background())
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
