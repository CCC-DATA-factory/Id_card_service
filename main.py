"""
main.py

FastAPI backend service for server-to-server communication.

This service exposes API endpoints defined in `routes.py` and restricts access
to a single trusted client IP address for security.

Features:
- IP allowlisting middleware to restrict access to known server(s)
- Secure HTTP headers middleware to improve security
- Request and response logging for audit and debugging
- Healthcheck endpoint for uptime monitoring
- Swagger/OpenAPI docs disabled for production
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from limiter_config import limiter 
from routes import router

ALLOWED_IPS = {
    "127.0.0.1",  
}


app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    """
    Add security headers to every HTTP response.

    Headers:
    - X-Content-Type-Options: Prevents MIME sniffing
    - X-Frame-Options: Prevents clickjacking via iframes
    - X-XSS-Protection: Enables XSS filter in browsers
    - Strict-Transport-Security: Enforces HTTPS for 2 years
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.middleware("http")
async def ip_allowlist(request: Request, call_next):
    """
    Allow only requests from IPs in the ALLOWED_IPS set.

    Uses the X-Forwarded-For header if behind a proxy, otherwise
    falls back to the client IP directly.
    
    Returns 403 Forbidden if IP not allowed.
    """
    client_ip = request.headers.get("X-Forwarded-For")
    if client_ip:
        # Take the first IP in X-Forwarded-For list (the original client)
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host

    if client_ip not in ALLOWED_IPS:
        return JSONResponse(status_code=403, content={"detail": "Access forbidden: IP not allowed"})

    return await call_next(request)


os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/service.log"), 
        logging.StreamHandler()                   
    ]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log incoming requests and corresponding response status.
    """
    logging.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logging.info(f"Response status: {response.status_code}")
    return response


app.include_router(router)



@app.get("/health")
def health():
    """
    Simple healthcheck endpoint for monitoring uptime.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
