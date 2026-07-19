from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["preferences"])
preferences_router = router

@preferences_router.get("/preferences/digest", response_model=DigestPreferences)
def get_digest_preferences(
    current_user: UserContext = Depends(get_current_user),
    repo: PreferencesRepository = Depends(get_preferences_repository),
) -> DigestPreferences:
    preferences = repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, utc_now())
    return to_digest_preferences_response(preferences)


@preferences_router.put("/preferences/digest", response_model=DigestPreferences)
def update_digest_preferences(
    payload: DigestPreferencesUpdate,
    current_user: UserContext = Depends(get_current_user),
    repo: PreferencesRepository = Depends(get_preferences_repository),
) -> DigestPreferences:
    now = utc_now()
    current = repo.get_preferences(current_user.user_id) or default_digest_preferences(current_user.user_id, now)
    updates = payload.model_dump(exclude_unset=True)
    updated = current.model_copy(update={**updates, "updated_at": now})

    return to_digest_preferences_response(repo.save_preferences(updated))
