import uuid

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CrudServiceDep, CurrentUser, ItemRepositoryDep
from app.schemas.items import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
def read_items(
    item_repository: ItemRepositoryDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> ItemsPublic:
    """
    Retrieve items.
    """

    if current_user.is_superuser:
        count = item_repository.count()
        items = item_repository.get_all(offset=skip, limit=limit)
    else:
        count = item_repository.count_by_owner_id(owner_id=current_user.id)
        items = item_repository.get_all_by_owner_id(
            owner_id=current_user.id, offset=skip, limit=limit
        )

    return ItemsPublic(
        data=[ItemPublic.model_validate(item) for item in items], count=count
    )


@router.get("/{id}")
def read_item(
    item_repository: ItemRepositoryDep, current_user: CurrentUser, id: uuid.UUID
) -> ItemPublic:
    """
    Get item by ID.
    """
    item = item_repository.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return ItemPublic.model_validate(item)


@router.post("/")
def create_item(
    *, crud_service: CrudServiceDep, current_user: CurrentUser, item_in: ItemCreate
) -> ItemPublic:
    """
    Create new item.
    """
    return crud_service.create_item(item_create=item_in, owner_id=current_user.id)


@router.put("/{id}")
def update_item(
    *,
    item_repository: ItemRepositoryDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> ItemPublic:
    """
    Update an item.
    """
    item = item_repository.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item_repository.update(item, update_dict)
    return ItemPublic.model_validate(item)


@router.delete("/{id}")
def delete_item(
    item_repository: ItemRepositoryDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = item_repository.get(id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    item_repository.delete(item)
    return Message(message="Item deleted successfully")
