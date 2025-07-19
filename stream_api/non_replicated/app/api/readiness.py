"""
Readiness Endpoint for Stream API

This module defines the `/ready` endpoint, used by deployment platforms or orchestrators
(e.g., Docker Swarm, Kubernetes, or health probes) to verify that the service instance
is ready to accept incoming requests.

Readiness Criteria:
    - Kafka dispatcher has successfully connected to the Kafka broker and obtained partition assignments.

Response Format:
    - HTTP 200 with {"status": "ready"} if the service is ready.
    - HTTP 503 with {"status": "not ready", "issues": <message>} if not.

Usage:
    This endpoint is typically called periodically by orchestration systems
    to determine if the service instance should receive traffic.
"""

from fastapi import Request
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from stream_api.non_replicated.app.core.kafka_dispatcher import KafkaDispatcher

router = APIRouter()


@router.get("/ready", tags=["Readiness"])
async def readiness_probe(request: Request):
    """
    Readiness probe endpoint.

    Returns:
        Dict: A dictionary indicating readiness status.
              If ready, returns {"status": "ready"} with HTTP 200.
              If not ready, returns HTTP 503 with content {"status": "not ready", "issues": <message>}.
    """
    dispatcher: KafkaDispatcher = request.app.state.kafka_dispatcher
    ready, message = dispatcher.is_kafka_connected()
    if not ready:
        return JSONResponse(status_code=503, content={"status": "not ready", "issues": message})
    return {"status": "ready"}
