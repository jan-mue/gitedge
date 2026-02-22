from app.schemas.items import ItemCreate, ItemPublic
from app.services.crud import CrudService
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_item(crud: CrudService) -> ItemPublic:
    user = create_random_user(crud)
    owner_id = user.id
    assert owner_id is not None
    title = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(title=title, description=description)
    return crud.create_item(item_create=item_in, owner_id=owner_id)
