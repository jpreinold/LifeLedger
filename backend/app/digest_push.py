from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import Settings, get_settings
from app.digest import build_daily_digest_summary
from app.models import UserPreferences
from app.preferences_repository import PreferencesRepository
from app.push_repository import PushSubscriptionRepository
from app.push_sender import InvalidPushSubscriptionError, PushPayload, PushSendError, PushSender, PyWebPushSender
from app.repository import ReminderRepository
from app.repository_factory import create_preferences_repository, create_push_subscription_repository, create_repository

DIGEST_PUSH_TITLE = "LifeLedger Digest"
DIGEST_PUSH_URL = "/?openDigest=1"
DIGEST_PUSH_TAG = "daily-digest"
DIGEST_PUSH_TYPE = "daily_digest"
DEFAULT_DIGEST_WINDOW_MINUTES = 15


@dataclass(frozen=True)
class DigestPushRunResult:
    checked_users: int = 0
    due_users: int = 0
    skipped_config_missing: bool = False
    skipped_no_preferences: int = 0
    skipped_not_due: int = 0
    skipped_duplicate: int = 0
    skipped_empty_digest: int = 0
    sent: int = 0
    failed: int = 0
    disabled_invalid: int = 0

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def run_daily_digest_push(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    reminder_repository: ReminderRepository | None = None,
    preferences_repository: PreferencesRepository | None = None,
    push_repository: PushSubscriptionRepository | None = None,
    sender: PushSender | None = None,
    schedule_window_minutes: int = DEFAULT_DIGEST_WINDOW_MINUTES,
) -> DigestPushRunResult:
    resolved_settings = settings or get_settings()
    if sender is None and not resolved_settings.push_notifications_configured:
        return DigestPushRunResult(skipped_config_missing=True)

    now_utc = normalize_utc(now or datetime.now(timezone.utc))
    reminders_repo = reminder_repository or create_repository(resolved_settings)
    preferences_repo = preferences_repository or create_preferences_repository(resolved_settings)
    subscriptions_repo = push_repository or create_push_subscription_repository(resolved_settings)
    push_sender = sender or PyWebPushSender(resolved_settings)

    checked_users = 0
    due_users = 0
    skipped_no_preferences = 0
    skipped_not_due = 0
    skipped_duplicate = 0
    skipped_empty_digest = 0
    sent = 0
    failed = 0
    disabled_invalid = 0

    for user_id in subscriptions_repo.list_user_ids_with_active_subscriptions():
        checked_users += 1
        preferences = preferences_repo.get_preferences(user_id)
        if preferences is None:
            skipped_no_preferences += 1
            continue

        local_now = to_user_local_datetime(now_utc, preferences.timezone)
        if not is_digest_due(preferences, local_now, schedule_window_minutes):
            skipped_not_due += 1
            continue

        if was_pushed_today(preferences, local_now):
            skipped_duplicate += 1
            continue

        subscriptions = subscriptions_repo.list_subscriptions(user_id)
        if not subscriptions:
            continue

        digest = build_daily_digest_summary(
            reminders_repo.list_reminders(user_id),
            lookahead_days=preferences.digest_lookahead_days,
            now=now_utc,
            current_day=local_now.date(),
        )
        if not digest.has_items:
            skipped_empty_digest += 1
            continue

        due_users += 1
        payload = PushPayload(
            title=DIGEST_PUSH_TITLE,
            body=digest.to_push_body(),
            url=DIGEST_PUSH_URL,
            tag=DIGEST_PUSH_TAG,
            type=DIGEST_PUSH_TYPE,
        )
        user_success = False

        for subscription in subscriptions:
            try:
                push_sender.send(subscription, payload)
            except InvalidPushSubscriptionError:
                disabled_invalid += 1
                failed += 1
                subscriptions_repo.save_subscription(
                    subscription.model_copy(
                        update={
                            "disabled_at": now_utc,
                            "last_failure_at": now_utc,
                            "failure_count": subscription.failure_count + 1,
                            "updated_at": now_utc,
                        }
                    )
                )
            except (PushSendError, Exception):
                failed += 1
                subscriptions_repo.save_subscription(
                    subscription.model_copy(
                        update={
                            "last_failure_at": now_utc,
                            "failure_count": subscription.failure_count + 1,
                            "updated_at": now_utc,
                        }
                    )
                )
            else:
                user_success = True
                sent += 1
                subscriptions_repo.save_subscription(
                    subscription.model_copy(
                        update={
                            "last_success_at": now_utc,
                            "failure_count": 0,
                            "updated_at": now_utc,
                        }
                    )
                )

        if user_success:
            preferences_repo.save_preferences(
                preferences.model_copy(update={"digest_last_pushed_at": now_utc, "updated_at": now_utc})
            )

    return DigestPushRunResult(
        checked_users=checked_users,
        due_users=due_users,
        skipped_no_preferences=skipped_no_preferences,
        skipped_not_due=skipped_not_due,
        skipped_duplicate=skipped_duplicate,
        skipped_empty_digest=skipped_empty_digest,
        sent=sent,
        failed=failed,
        disabled_invalid=disabled_invalid,
    )


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_user_local_datetime(now_utc: datetime, timezone_name: str | None) -> datetime:
    try:
        user_timezone = ZoneInfo(timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        user_timezone = timezone.utc

    return now_utc.astimezone(user_timezone)


def is_digest_due(preferences: UserPreferences, local_now: datetime, schedule_window_minutes: int) -> bool:
    if not preferences.digest_enabled:
        return False

    hour_text, minute_text = preferences.digest_time.split(":", maxsplit=1)
    target = local_now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
    elapsed = local_now - target
    return timedelta(0) <= elapsed < timedelta(minutes=schedule_window_minutes)


def was_pushed_today(preferences: UserPreferences, local_now: datetime) -> bool:
    if preferences.digest_last_pushed_at is None:
        return False

    pushed_at = normalize_utc(preferences.digest_last_pushed_at).astimezone(local_now.tzinfo)
    return pushed_at.date() == local_now.date()
