from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["push"])
push_router = router

@push_router.get("/push/config", response_model=PushConfigurationResponse)
def get_push_configuration(
    _current_user: UserContext = Depends(get_current_user),
    app_settings: Settings = Depends(get_app_settings),
) -> PushConfigurationResponse:
    return PushConfigurationResponse(configured=app_settings.push_notifications_configured)


@push_router.get("/push/status", response_model=PushStatusResponse)
def get_push_status(
    current_user: UserContext = Depends(get_current_user),
    preferences_repo: PreferencesRepository = Depends(get_preferences_repository),
    push_repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
    app_settings: Settings = Depends(get_app_settings),
) -> PushStatusResponse:
    subscriptions = push_repo.list_subscriptions(current_user.user_id)
    preferences = preferences_repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, utc_now())
    return to_push_status_response(app_settings, subscriptions, preferences)


@push_router.post("/push/test", response_model=PushTestResponse)
def send_test_push(
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
    app_settings: Settings = Depends(get_app_settings),
    sender: PushSender = Depends(get_push_sender),
) -> PushTestResponse:
    if not app_settings.push_notifications_configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=PUSH_CONFIG_MISSING_DETAIL)

    subscriptions = repo.list_subscriptions(current_user.user_id)
    if not subscriptions:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NO_ACTIVE_PUSH_SUBSCRIPTION_DETAIL)

    now = utc_now()
    sent = 0

    for subscription in subscriptions:
        try:
            sender.send(subscription, TEST_PUSH_PAYLOAD)
        except PushConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=PUSH_CONFIG_MISSING_DETAIL) from exc
        except InvalidPushSubscriptionError:
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "disabled_at": now,
                        "last_failure_at": now,
                        "failure_count": subscription.failure_count + 1,
                        "updated_at": now,
                    }
                )
            )
        except (PushSendError, Exception):
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "last_failure_at": now,
                        "failure_count": subscription.failure_count + 1,
                        "updated_at": now,
                    }
                )
            )
        else:
            sent += 1
            repo.save_subscription(
                subscription.model_copy(
                    update={
                        "last_success_at": now,
                        "failure_count": 0,
                        "updated_at": now,
                    }
                )
            )

    if sent == 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to send test push.")

    return PushTestResponse(sent=sent)


@push_router.get("/push/subscriptions", response_model=list[PushSubscriptionResponse])
def list_push_subscriptions(
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> list[PushSubscriptionResponse]:
    return [to_push_subscription_response(subscription) for subscription in repo.list_subscriptions(current_user.user_id)]


@push_router.post("/push/subscriptions", response_model=PushSubscriptionResponse)
def save_push_subscription(
    payload: PushSubscriptionCreate,
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> PushSubscriptionResponse:
    now = utc_now()
    existing = repo.get_subscription_by_endpoint(current_user.user_id, payload.endpoint)
    subscription = PushSubscription(
        user_id=current_user.user_id,
        subscription_id=existing.subscription_id if existing else push_subscription_id_for_endpoint(payload.endpoint),
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=payload.user_agent,
        created_at=existing.created_at if existing else now,
        updated_at=now,
        disabled_at=None,
        last_success_at=existing.last_success_at if existing else None,
        last_failure_at=None,
        failure_count=0,
    )

    return to_push_subscription_response(repo.save_subscription(subscription))


@push_router.delete("/push/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_subscription(
    subscription_id: str,
    current_user: UserContext = Depends(get_current_user),
    repo: PushSubscriptionRepository = Depends(get_push_subscription_repository),
) -> Response:
    disabled = repo.disable_subscription(current_user.user_id, subscription_id, utc_now())
    if not disabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push subscription not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
