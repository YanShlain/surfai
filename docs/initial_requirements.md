# Flight Booking System - Temporal Architecture

This document outlines the flight booking flow from the User through the Web App, RESTful Server, Temporal, and finally to the Workers.

## User Flow Exercise
**Scenario:** Flight seat reservation and payment system with timeouts and validation.

---

## Architecture Components

* **User:** Customer booking flights, selecting seats, and making payments.
* **Web App:** Frontend showing real-time seat timer, order status, and booking interface.
* **RESTful Server (go):** Go-based APIs for flight management, payment gateway integration, and order processing.
* **Temporal Server:** Orchestrates complex booking workflows with timeouts and state management.
* **Workers (go):** Execute specific booking activities and handle business logic.

---

## Business Logic & System Layers

### 1. User Layer
* **User:** Creates Flight Order, Selects $N$ Seats, Reviews & Pays.
* **Web App:** Real-time Status, Seat Timer Display, Order Updates.

### 2. Application Layer
* **RESTful Server (go):** Flight APIs, Payment Gateway, Order Management.

### 3. Temporal Platform
* **Temporal Server (`temporal server start-dev`):** Workflow Orchestration, Timeout Management.
* **Temporal Workers (go):** Seat Reservation, Payment Processing, Timer Management.

### 4. Business Logic Details
* **Seat Reservation:** * Manages seat inventory and 15-minute seat holds.
    * Features refreshable timers that reset when the user updates their selection.
* **Payment Validation:** * Processes 5-digit payment codes with a 10-second timeout.
    * Includes 3 retry attempts and simulates a 15% failure rate.
* **Order Management:** * Tracks order status, handles failures gracefully, and sends confirmation messages.

---

## Mandatory Temporal Workflows
At the very least, you should have a temporal workflow that implements the entire order.

### Detailed User Flow
1.  **Create Flight Order:** User initiates the booking process.
2.  **Select N Seats:** User chooses seats, which starts the Seat Reservation Workflow (15-minute timer).
3.  **Review Order:** User can view the timer countdown and modify seat selections (the timer refreshes on changes).
4.  **Pay with 5-digit Code:** User enters the payment code to trigger Payment Code Validation.
5.  **Code Validation:** The system checks the code within 10 seconds.
    * **Success (85%):** Charges the user, processes the Order Management message, and sends a Confirmation.
    * **Failure (15%):** Retries up to 3 times. After 3 failures, the order fails with an indicative message.
6.  **Real-time Updates:** User always sees the seat timer countdown and order status.

---

## Business Rules Implemented by Temporal
* [x] Seat inventory management (implementation approach left to developer) 
* [x] 15-minute seat reservation with auto-release 
* [x] Timer refresh on seat updates 
* [x] 10-second payment validation timeout 
* [x] 3 retry attempts for failed payments 
* [x] 15% payment failure simulation 
* [x] Real-time status tracking 
* [x] Graceful failure handling with user feedback 

---

## Implementation Notes

* **Seat Management:** The system must handle seat inventory internally—this is not delegated to external microservices.
* **Flexible Approaches:** The implementation approach is flexible and could include:
    * Custom data structures with conflict resolution 
    * In-memory state with persistence 
    * Temporal Entity Workflows for seat state management 
    * Traditional database with transaction management 
    * *Choice of approach is completely left to the implementer.*
* **Diagram Notation:** The solid arrows show the primary request flow, while the dotted arrows show the response/result flow back to the user.