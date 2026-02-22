from fastapi import APIRouter

from .routers import (
    admin_access_router,
    agent_execution_router,
    auth_profile_router,
    conversations_runs_router,
    health_router,
    notifications_router,
    permission_requests_router,
)

router = APIRouter()
router.include_router(auth_profile_router)
router.include_router(agent_execution_router)
router.include_router(conversations_runs_router)
router.include_router(admin_access_router)
router.include_router(permission_requests_router)
router.include_router(notifications_router)
router.include_router(health_router)
