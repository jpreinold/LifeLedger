from app.route_support import *  # noqa: F403
from app.routers.account import router as account_router
from app.routers.captures import router as captures_router
from app.routers.documents import router as documents_router
from app.routers.health import router as health_router
from app.routers.integrations import router as integrations_router
from app.routers.lifecycle import router as lifecycle_router
from app.routers.preferences import router as preferences_router
from app.routers.push import router as push_router
from app.routers.records import router as records_router
from app.routers.relationships import router as relationships_router
from app.routers.reminders import router as reminders_router
from app.routers.search import router as search_router

app = FastAPI(title="LifeLedger API", version="0.1.0")  # noqa: F405

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(account_router)


@app.exception_handler(RequestValidationError)
async def sanitize_sensitive_validation_errors(request: Request, exc: RequestValidationError):
    if "/protected" not in request.url.path and "/fields" not in request.url.path:
        return await request_validation_exception_handler(request, exc)

    safe_errors = []
    for error in exc.errors():
        safe_error = {key: error[key] for key in ("type", "loc", "msg") if key in error}
        safe_errors.append(safe_error)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": safe_errors},
        headers=no_store_headers(),
    )


@app.middleware("http")
async def no_store_attachment_responses(request: Request, call_next):
    response = await call_next(request)
    if (
        "/attachments" in request.url.path
        or "/fields/" in request.url.path
        or "/protected" in request.url.path
        or "/history" in request.url.path
        or "/activity" in request.url.path
        or "/responsibility-events/" in request.url.path
        or request.url.path.startswith("/account")
        or request.url.path.startswith("/captures")
        or request.url.path.startswith("/proposals")
        or request.url.path.startswith("/ai-")
    ):
        for header, value in no_store_headers().items():
            response.headers[header] = value
    return response


@app.middleware("http")
async def block_data_access_while_account_is_deleting(request: Request, call_next):
    account_exempt = request.url.path.startswith("/account") or request.url.path in {"/health", "/version"}
    if request.method != "OPTIONS" and not account_exempt:
        try:
            user = get_current_user(request)
            lifecycle = get_account_operations_repository().get_lifecycle(user.user_id)
        except HTTPException:
            return await call_next(request)
        if lifecycle.state in {
            AccountState.DELETION_REQUESTED,
            AccountState.DELETING,
            AccountState.DELETION_REQUIRES_ATTENTION,
            AccountState.DELETED,
        }:
            is_write = request.method not in {"GET", "HEAD"}
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": {
                        "code": "deletion_in_progress" if is_write else "account_unavailable",
                        "message": (
                            "New changes are unavailable while account deletion is in progress."
                            if is_write
                            else "Account data is unavailable while deletion is in progress."
                        ),
                    }
                },
                headers=no_store_headers(),
            )
    return await call_next(request)

for context_router in (
    search_router,
    records_router,
    documents_router,
    relationships_router,
    preferences_router,
    integrations_router,
    push_router,
    reminders_router,
    lifecycle_router,
    captures_router,
):
    app.include_router(context_router)

