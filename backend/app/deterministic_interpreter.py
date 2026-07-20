from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import calendar
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.capture_models import (
    ActionSeed,
    ActionType,
    ConfidenceCategory,
    EntityCandidate,
    StructuredInterpretation,
)
from app.entity_resolution_service import EntityResolutionService
from app.schemas import RecordType


MONTHS = {name.casefold(): index for index, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.casefold(): index for index, name in enumerate(calendar.month_abbr) if name})
WEEKDAYS = {name.casefold(): index for index, name in enumerate(calendar.day_name)}


class DeterministicInterpreter:
    def __init__(self, entities: EntityResolutionService):
        self.entities = entities

    def interpret(
        self,
        *,
        user_id: str,
        text: str,
        captured_at: datetime,
        timezone_name: str,
    ) -> tuple[StructuredInterpretation | None, list[EntityCandidate]]:
        local_now = _local_now(captured_at, timezone_name)
        value = " ".join(text.strip().split())

        result = self._explicit_reminder(value, local_now)
        if result:
            return result, []

        candidates = self.entities.retrieve(user_id, value, limit=12)
        for parser in (self._birthday, self._complete, self._snooze, self._expires):
            result = parser(value, local_now, candidates)
            if result:
                return result, candidates
        return None, candidates

    def _explicit_reminder(self, text: str, now: datetime) -> StructuredInterpretation | None:
        match = re.fullmatch(
            r"remind me (?P<when>.+?)(?: at (?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)?)? to (?P<title>.+?)[.!]?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        due = parse_date_phrase(match.group("when"), now.date())
        if due is None:
            return None
        reminder_time = None
        if match.group("hour"):
            hour = int(match.group("hour"))
            minute = int(match.group("minute") or 0)
            ampm = (match.group("ampm") or "").casefold().replace(".", "")
            if hour > 23 or minute > 59 or (ampm and not 1 <= hour <= 12):
                return None
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            elif not ampm and 1 <= hour <= 6:
                # Quick-capture convention: bare early hours mean afternoon.
                hour += 12
            reminder_time = f"{hour:02d}:{minute:02d}"
        title = match.group("title").strip(" .")
        return _interpretation(
            "Create one reminder for your request.",
            [
                ActionSeed(
                    action_type=ActionType.CREATE_RESPONSIBILITY,
                    fields={
                        "title": title[0].upper() + title[1:],
                        "category": "Other",
                        "due_date": due.isoformat(),
                        "repeat": "None",
                        "priority": "Medium",
                        "reminder_time": reminder_time,
                        "reminder_type": "generic",
                    },
                    explanation=f"Create a reminder for {title}.",
                )
            ],
        )

    def _birthday(
        self, text: str, now: datetime, candidates: list[EntityCandidate]
    ) -> StructuredInterpretation | None:
        match = re.fullmatch(
            r"(?:it(?:'|’)s|today is)\s+(?:my\s+)?(?:(?P<relationship>friend|family member|coworker|neighbor)\s+)?(?P<name>[\w .'-]+?)(?:'|’)s birthday(?: today)?[.!]?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        name = match.group("name").strip().title()
        relationship = _relationship_label(match.group("relationship"))
        birthday = f"--{now.month:02d}-{now.day:02d}"
        people = [
            item
            for item in candidates
            if item.entity_type == "item" and item.item_type == RecordType.PERSON and _name_matches(name, item)
        ]
        if len(people) > 1:
            return StructuredInterpretation(
                supported=True,
                confidence=ConfidenceCategory.LOW,
                summary=f"I found more than one Person named {name}.",
                actions=[
                    ActionSeed(
                        action_type=ActionType.UPDATE_ITEM_DETAIL,
                        item_type=RecordType.PERSON,
                        fields={"detail_key": "birthday", "value": birthday},
                        explanation=f"Save today's month and day as {name}'s birthday.",
                    ),
                ],
                ambiguity_reasons=[f"Multiple people named {name} match this capture."],
                missing_information=[f"Which {name} did you mean?"],
            )
        if len(people) == 1:
            target = people[0].entity_id
            return _interpretation(
                f"Save {now.strftime('%B')} {now.day} as {name}'s birthday. LifeLedger will maintain the annual reminder.",
                [
                    ActionSeed(
                        action_type=ActionType.UPDATE_ITEM_DETAIL,
                        target_item_id=target,
                        item_type=RecordType.PERSON,
                        fields={"detail_key": "birthday", "value": birthday},
                        explanation=f"Save today's month and day as {name}'s birthday.",
                    ),
                ],
            )
        details = {"birthday": birthday}
        if relationship:
            details["relationship_context"] = relationship
        return _interpretation(
            f"Create {name} as a Person and save the birthday. LifeLedger will maintain the annual reminder.",
            [
                ActionSeed(
                    action_type=ActionType.CREATE_ITEM,
                    item_type=RecordType.PERSON,
                    fields={"title": name, "details": details},
                    explanation=f"Create {name} as a Person.",
                ),
            ],
        )

    def _complete(self, text: str, now: datetime, candidates: list[EntityCandidate]) -> StructuredInterpretation | None:
        match = re.fullmatch(
            r"(?:mark (?P<mark>.+?) complete|i (?:completed|finished|changed|replaced) (?P<done>.+?)(?: today)?)\.?",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        subject = (match.group("mark") or match.group("done")).strip()
        matches = _responsibility_matches(subject, candidates)
        target = matches[0].entity_id if len(matches) == 1 else None
        ambiguity = [] if len(matches) == 1 else [f"I could not identify one responsibility for “{subject}”."]
        return StructuredInterpretation(
            supported=True,
            confidence=ConfidenceCategory.HIGH if target else ConfidenceCategory.LOW,
            summary=f"Mark {subject} complete.",
            actions=[
                ActionSeed(
                    action_type=ActionType.COMPLETE_RESPONSIBILITY,
                    target_responsibility_id=target,
                    fields={"completed_on": now.date().isoformat()},
                    explanation=f"Record {subject} as completed today.",
                )
            ],
            ambiguity_reasons=ambiguity,
            missing_information=[f"Which responsibility did you complete?"] if ambiguity else [],
        )

    def _snooze(self, text: str, now: datetime, candidates: list[EntityCandidate]) -> StructuredInterpretation | None:
        match = re.fullmatch(r"snooze (?P<title>.+?) until (?P<when>.+?)[.]?", text, flags=re.IGNORECASE)
        if not match:
            return None
        target_date = parse_date_phrase(match.group("when"), now.date())
        if target_date is None:
            return None
        subject = match.group("title").strip()
        matches = _responsibility_matches(subject, candidates)
        target = matches[0].entity_id if len(matches) == 1 else None
        snoozed = datetime.combine(target_date, time(9, 0), tzinfo=now.tzinfo).astimezone(timezone.utc)
        ambiguity = [] if target else [f"I could not identify one responsibility for “{subject}”."]
        return StructuredInterpretation(
            supported=True,
            confidence=ConfidenceCategory.HIGH if target else ConfidenceCategory.LOW,
            summary=f"Snooze {subject} until {target_date.isoformat()}.",
            actions=[
                ActionSeed(
                    action_type=ActionType.SNOOZE_RESPONSIBILITY,
                    target_responsibility_id=target,
                    fields={"snoozed_until": snoozed.isoformat()},
                    explanation=f"Snooze {subject} until the selected morning.",
                )
            ],
            ambiguity_reasons=ambiguity,
            missing_information=["Which responsibility should be snoozed?"] if ambiguity else [],
        )

    def _expires(self, text: str, _now: datetime, candidates: list[EntityCandidate]) -> StructuredInterpretation | None:
        match = re.fullmatch(r"(?P<title>.+?) expires (?:on )?(?P<when>.+?)[.]?", text, flags=re.IGNORECASE)
        if not match:
            return None
        expiration = parse_absolute_date(match.group("when"))
        if expiration is None:
            return None
        subject = match.group("title").strip()
        matches = [item for item in candidates if item.entity_type == "item" and _name_matches(subject, item)]
        target = matches[0].entity_id if len(matches) == 1 else None
        ambiguity = [] if target else [f"I could not identify one item for “{subject}”."]
        return StructuredInterpretation(
            supported=True,
            confidence=ConfidenceCategory.HIGH if target else ConfidenceCategory.LOW,
            summary=f"Update {subject}'s expiration date.",
            actions=[
                ActionSeed(
                    action_type=ActionType.UPDATE_ITEM_DETAIL,
                    target_item_id=target,
                    fields={"detail_key": "expiration_date", "value": expiration.isoformat()},
                    explanation=f"Set the expiration date to {expiration.isoformat()}.",
                )
            ],
            ambiguity_reasons=ambiguity,
            missing_information=["Which item has this expiration date?"] if ambiguity else [],
        )


def parse_date_phrase(value: str, today: date) -> date | None:
    normalized = " ".join(value.casefold().strip(" .").split())
    if normalized == "today":
        return today
    if normalized == "tomorrow":
        return today + timedelta(days=1)
    if normalized in WEEKDAYS:
        delta = (WEEKDAYS[normalized] - today.weekday()) % 7
        return today + timedelta(days=delta or 7)
    if normalized.startswith("next ") and normalized[5:] in WEEKDAYS:
        weekday = WEEKDAYS[normalized[5:]]
        delta = (weekday - today.weekday()) % 7
        return today + timedelta(days=(delta or 7))
    return parse_absolute_date(normalized, default_year=today.year)


def parse_absolute_date(value: str, *, default_year: int | None = None) -> date | None:
    normalized = " ".join(value.casefold().strip(" .").replace(",", " ").split())
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        pass
    match = re.fullmatch(r"(?P<month>[a-z]+) (?P<day>\d{1,2})(?: (?P<year>\d{4}))?", normalized)
    if not match or match.group("month") not in MONTHS:
        return None
    year = int(match.group("year")) if match.group("year") else default_year
    if year is None:
        return None
    try:
        return date(year, MONTHS[match.group("month")], int(match.group("day")))
    except ValueError:
        return None


def _interpretation(summary: str, actions: list[ActionSeed]) -> StructuredInterpretation:
    return StructuredInterpretation(
        supported=True,
        confidence=ConfidenceCategory.HIGH,
        summary=summary,
        actions=actions,
    )


def _local_now(value: datetime, timezone_name: str) -> datetime:
    source = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    return source.astimezone(zone)


def _relationship_label(value: str | None) -> str | None:
    if not value:
        return None
    return {"family member": "Family"}.get(value.casefold(), value.title())


def _name_matches(value: str, candidate: EntityCandidate) -> bool:
    normalized = value.casefold().strip(" .")
    return normalized == candidate.display_title.casefold() or any(normalized == alias.casefold() for alias in candidate.safe_aliases)


def _responsibility_matches(value: str, candidates: list[EntityCandidate]) -> list[EntityCandidate]:
    normalized = value.casefold().strip(" .")
    direct = [
        item
        for item in candidates
        if item.entity_type == "responsibility"
        and (normalized == item.display_title.casefold() or normalized in item.display_title.casefold())
    ]
    if direct:
        return direct
    linked = [
        item
        for item in candidates
        if item.entity_type == "item"
        and item.relevant_responsibility_id
        and (
            normalized in (item.relevant_responsibility_title or "").casefold()
            or any(token in normalized for token in (item.relevant_responsibility_title or "").casefold().split() if len(token) > 3)
        )
    ]
    return [
        EntityCandidate(
            entity_type="responsibility",
            entity_id=item.relevant_responsibility_id or "",
            display_title=item.relevant_responsibility_title or "Responsibility",
            relevant_responsibility_id=item.relevant_responsibility_id,
            relevant_responsibility_title=item.relevant_responsibility_title,
            relevant_dates=item.relevant_dates,
            match_reasons=["linked responsibility"],
            score=item.score,
        )
        for item in linked
    ]


def _next_month_day(today: date, month: int, day: int) -> date:
    target = date(today.year, month, day)
    return target if target >= today else date(today.year + 1, month, day)
