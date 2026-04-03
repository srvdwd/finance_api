from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login")
def login():
    return {"message": "Login endpoint"}

@router.post("/register")
def register():
    return {"message": "Register endpoint"}