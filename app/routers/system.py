from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return "\n".join(["User-agent: *", "Disallow: /showcase", "Disallow: /static/uploads/", ""])
