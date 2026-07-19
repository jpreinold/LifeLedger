from app.linked_items_repository import DynamoLinkedItemRepository
from app.responsibility_history_repository import DynamoResponsibilityHistoryRepository


class PagedTable:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def test_history_account_export_read_follows_every_dynamo_page():
    table = PagedTable(
        [
            {"Items": [{"event_id": "event-1"}], "LastEvaluatedKey": {"event_id": "event-1"}},
            {"Items": [{"event_id": "event-2"}]},
        ]
    )
    repository = DynamoResponsibilityHistoryRepository(
        "history", "reminders", "us-east-1", table=table, client=object()
    )
    repository._from_item = lambda item: item

    assert repository.list_for_user("user-a", limit=None) == [
        {"event_id": "event-1"},
        {"event_id": "event-2"},
    ]
    assert "Limit" not in table.calls[0]
    assert table.calls[1]["ExclusiveStartKey"] == {"event_id": "event-1"}


def test_relationship_account_export_read_follows_every_dynamo_page():
    table = PagedTable(
        [
            {"Items": [{"link_id": "link-1"}], "LastEvaluatedKey": {"link_id": "link-1"}},
            {"Items": [{"link_id": "link-2"}]},
        ]
    )
    repository = DynamoLinkedItemRepository("relationships", "us-east-1", table=table)
    repository._from_item = lambda item: item

    assert repository.list_for_user("user-a", limit=None) == [
        {"link_id": "link-1"},
        {"link_id": "link-2"},
    ]
    assert "Limit" not in table.calls[0]
    assert table.calls[1]["ExclusiveStartKey"] == {"link_id": "link-1"}
