from fastapi import APIRouter

from app.route_support import *  # noqa: F403

router = APIRouter(tags=["search"])
search_router = router

@search_router.get("/search", response_model=SearchResponse)
def search_items(
    q: str = Query(default="", max_length=120),
    item_types: str | None = Query(default=None, alias="itemTypes"),
    statuses: str | None = Query(default=None),
    archived: bool = Query(default=False),
    date_from: date | None = Query(default=None, alias="dateFrom"),
    date_to: date | None = Query(default=None, alias="dateTo"),
    category: str | None = Query(default=None, max_length=80),
    owner: str | None = Query(default=None, max_length=120),
    has_documents: bool | None = Query(default=None, alias="hasDocuments"),
    has_linked_items: bool | None = Query(default=None, alias="hasLinkedItems"),
    sort: SearchSort = Query(default=SearchSort.RELEVANCE),
    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize"),
    cursor: str | None = Query(default=None, max_length=512),
    current_user: UserContext = Depends(get_current_user),
    search_service: SearchQueryService = Depends(get_search_query_service),
) -> SearchResponse:
    started = time.perf_counter()
    try:
        request = validate_search_request(
            query=q,
            item_types=item_types,
            statuses=statuses,
            include_archived=archived,
            date_from=date_from,
            date_to=date_to,
            category=category,
            owner=owner,
            has_documents=has_documents,
            has_linked_items=has_linked_items,
            sort=sort,
            page_size=page_size,
            cursor=cursor,
        )
        result = search_service.search(current_user.user_id, request)
    except SearchValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "search_request",
        extra={
            "operation": "search",
            "query_present": bool(q.strip()),
            "query_length": len(q.strip()),
            "filter_types": sorted(key for key, value in result.applied_filters.items() if value not in (None, "", [], False)),
            "sort": sort.value,
            "page_size": page_size,
            "result_count": result.result_count,
            "has_next_page": result.next_cursor is not None,
            "latency_ms": latency_ms,
        },
    )
    return result


@search_router.get("/saved-views", response_model=list[SavedSearchViewResponse])
def list_saved_views(
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> list[SavedSearchViewResponse]:
    return [to_saved_view_response(view) for view in service.list_views(current_user.user_id)]


@search_router.post("/saved-views", response_model=SavedSearchViewResponse, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedSearchViewCreate,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    saved = service.create_view(
        user_id=current_user.user_id,
        saved_view_id=str(uuid4()),
        name=payload.name,
        query=payload.query,
        filters=payload.filters,
        sort=payload.sort,
        icon=payload.icon,
        is_pinned=payload.is_pinned,
        now=utc_now(),
    )
    return to_saved_view_response(saved)


@search_router.get("/saved-views/{saved_view_id}", response_model=SavedSearchViewResponse)
def get_saved_view(
    saved_view_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    view = service.get_view(current_user.user_id, saved_view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return to_saved_view_response(view)


@search_router.patch("/saved-views/{saved_view_id}", response_model=SavedSearchViewResponse)
def update_saved_view(
    saved_view_id: str,
    payload: SavedSearchViewUpdate,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> SavedSearchViewResponse:
    view = service.get_view(current_user.user_id, saved_view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    updated = service.update_view(
        view,
        name=payload.name,
        query=payload.query,
        filters=payload.filters,
        sort=payload.sort,
        icon=payload.icon,
        is_pinned=payload.is_pinned,
        now=utc_now(),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return to_saved_view_response(updated)


@search_router.delete("/saved-views/{saved_view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_view(
    saved_view_id: str,
    current_user: UserContext = Depends(get_current_user),
    service: SavedSearchViewService = Depends(get_saved_search_view_service),
) -> Response:
    if not service.delete_view(current_user.user_id, saved_view_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
