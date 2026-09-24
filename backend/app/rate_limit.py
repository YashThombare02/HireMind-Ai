from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared instance: routers import `limiter` to decorate endpoints, main.py
# attaches it to app.state and registers the exception handler + middleware.
limiter = Limiter(key_func=get_remote_address)
