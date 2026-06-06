"""
Health check endpoint — verifies all critical dependencies are alive.

Used by:
  - Monitoring tools (UptimeRobot, Grafana, etc.)
  - PFE demo: proves the system is running before a live demo
  - Debugging: quickly see which dependency is down
"""
import logging
import os
import time

import redis
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

_boot_time = time.time()


@require_http_methods(["GET"])
def health_check(request):
    """
    GET /api/v1/health/
    No authentication required — this is a public liveness probe.
    """
    checks = {}
    overall_ok = True

    # 1. PostgreSQL
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "error", "detail": str(exc)}
        overall_ok = False

    # 2. Redis (latency tracking cache on DB 1)
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        r = redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}
        overall_ok = False

    # 3. ML Models (M1 Gatekeeper + M2 Classifier)
    try:
        from ml_pipeline.models_pkg.inference import AEGISPipeline
        pipeline = AEGISPipeline.get_instance()
        if pipeline is not None:
            checks["ml_models"] = {
                "status": "ok",
                "device": str(pipeline.device),
                "m1_loaded": pipeline.m1_model is not None,
                "m2_loaded": pipeline.m2_model is not None,
            }
        else:
            checks["ml_models"] = {"status": "error", "detail": "Pipeline not initialized"}
            overall_ok = False
    except Exception as exc:
        checks["ml_models"] = {"status": "error", "detail": str(exc)}
        overall_ok = False

    # 4. Groq API Key (Agent 3 — LLM Auditor)
    groq_key = os.getenv("GROQ_API_KEY", "").strip().strip('"')
    if groq_key:
        checks["groq_llm"] = {"status": "ok", "key_present": True}
    else:
        checks["groq_llm"] = {"status": "error", "detail": "GROQ_API_KEY not set"}
        overall_ok = False

    # 5. Evolution API Key
    evo_key = os.getenv("EVOLUTION_API_KEY", "").strip()
    if evo_key:
        checks["evolution_api"] = {"status": "ok", "key_present": True}
    else:
        checks["evolution_api"] = {"status": "error", "detail": "EVOLUTION_API_KEY not set"}
        overall_ok = False

    uptime_seconds = int(time.time() - _boot_time)

    return JsonResponse({
        "status": "healthy" if overall_ok else "degraded",
        "checks": checks,
        "uptime_seconds": uptime_seconds,
    }, status=200 if overall_ok else 503)
