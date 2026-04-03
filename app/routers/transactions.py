from fastapi import APIRouter

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("/")
def get_transactions():
    return {"message": "Transactions endpoint"}