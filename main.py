import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routes import activity, dashboard, findings, github, health, repositories, reviews, users, webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oasis")

app = FastAPI(title="Oasis DevSecOps Engine", version="3.1")

                                                                         
                                                                       
                                                                   
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalizes every HTTPException into the {"error": {code, message}}
    envelope (task section 34), whether it was raised with a dict detail
    (our own service-layer errors) or a plain string (FastAPI/framework
    defaults, e.g. the webhook's signature/malformed-payload errors).
    """
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body = {"error": detail}
    else:
        body = {"error": {"code": f"HTTP_{exc.status_code}", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: never leak a stack trace or exception internals
    to the client. Full detail goes to the server log only."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )


if missing := settings.missing_required():
    logger.warning(
        "Starting with missing configuration: %s. Dependent routes will return clear errors instead of "
        "crashing, but should be configured before relying on them.",
        ", ".join(missing),
    )

                                                                      
                                                                  
app.include_router(health.router)
app.include_router(webhook.router)

                                              
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(repositories.router)
app.include_router(findings.router)
app.include_router(reviews.router)
app.include_router(activity.router)
app.include_router(github.router)
