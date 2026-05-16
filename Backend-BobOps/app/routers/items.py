from fastapi import APIRouter

router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "Not found"}}
)

@router.get("/")
async def read_items():
    return [
        {
            "item_id": "1",
            "name": "Morty's Hammer"
        }, 
        {
            "item_id": "2",
            "name": "Rick's Portal Gun"
        },
        {
            "item_id": "3",
            "name": "Meeseeks-Box"
        },
        {
            "item_id": "4",
            "name": "Microverse"
        },
        {
            "item_id": "5",
            "name": "Squanchy"
        },
    ]

@router.get("/{item_id}")
async def read_item(item_id: str):
    return {"item_id": item_id}