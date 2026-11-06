from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.students import router as students_router

__all__ = ["health_router", "chat_router", "students_router"]
