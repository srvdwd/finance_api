from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/summary")
def get_summary():
    return {"message": "Analytics summary"}