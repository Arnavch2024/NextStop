from app.routers.agent_runs import router as agent_runs_router
from app.routers.campus_hiring import router as campus_hiring_router
from app.routers.chat import router as chat_router
from app.routers.contacts import router as contacts_router
from app.routers.demo_auth import router as demo_auth_router
from app.routers.health import router as health_router
from app.routers.outreach import router as outreach_router
from app.routers.scores import router as scores_router
from app.routers.student_records import router as student_records_router
from app.routers.students import router as students_router
from app.routers.voice import router as voice_router

__all__ = [
    "health_router",
    "chat_router",
    "students_router",
    "voice_router",
    "outreach_router",
    "contacts_router",
    "agent_runs_router",
    "scores_router",
    "demo_auth_router",
    "student_records_router",
    "campus_hiring_router",
]
