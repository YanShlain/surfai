package api

import (
	"github.com/gin-gonic/gin"

	"neon/domain"
	"neon/internal/api/handler"
	"neon/internal/web"
)

// NewRouter registers MVP-A read endpoints and static UI.
func NewRouter(flights domain.FlightRepository, seats domain.SeatRepository) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())

	staticFS := web.MustFS()
	web.Register(r, staticFS)

	h := handler.NewFlightHandler(flights, seats)
	v1 := r.Group("/api/v1")
	{
		v1.GET("/flights", h.ListFlights)
		v1.GET("/flights/:flight_id/seats", h.GetSeatMap)
	}
	return r
}
