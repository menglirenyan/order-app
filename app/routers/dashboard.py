from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.templating import templates
from ..core.web import get_current_user, require_login
from ..db import get_db
from ..services.orders import get_dashboard_data

router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    context = get_dashboard_data(db)
    context.update(current_user=get_current_user(request, db), active_nav="dashboard")
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)
