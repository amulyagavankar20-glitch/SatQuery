import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Attach the request ID to the request state so routes can access it
        request.state.request_id = request_id
        
        # Call the next middleware / route handler
        response = await call_next(request)
        
        # Attach the request ID to the response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
