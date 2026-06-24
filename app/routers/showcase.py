from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..core.templating import templates
from ..core.web import add_flash, get_current_user, require_login
from ..db import get_db
from ..services import showcase as showcase_service
from ..services.quotation import build_quote_excel, build_quote_image, normalize_quote_rows

router = APIRouter()


@router.get("/showcase")
def showcase_public(request: Request, category: str = "", q: str = "", db: Session = Depends(get_db)):
    items, categories = showcase_service.list_public_items(db, category, q)
    return templates.TemplateResponse(
        request=request, name="showcase.html",
        context={
            "items": items, "categories": categories,
            "current_category": category, "current_query": q.strip(),
        },
    )


@router.get("/showcase/manage")
def showcase_manage(request: Request, category: str = "", db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request, name="showcase_manage.html",
        context={
            "items": showcase_service.list_manage_items(db, category),
            "current_user": get_current_user(request, db),
            "categories": showcase_service.get_category_options(db),
            "current_category": category.strip(), "active_nav": "showcase_manage",
        },
    )


@router.get("/showcase/manage/new")
def showcase_new_page(request: Request, db: Session = Depends(get_db)):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request, name="showcase_new.html",
        context={
            "error": "", "current_user": get_current_user(request, db),
            "categories": showcase_service.get_category_options(db), "active_nav": "showcase_manage",
        },
    )


@router.post("/showcase/manage/new")
def showcase_new_submit(
    request: Request,
    title: str = Form(...), category: str = Form(""), image_file: UploadFile = File(None),
    description: str = Form(""), is_visible: str = Form("true"),
    db: Session = Depends(get_db),
):
    redirect = require_login(request)
    if redirect:
        return redirect
    current_user = get_current_user(request, db)
    try:
        item, error = showcase_service.create_item(
            db, title, category, image_file, description, is_visible == "true"
        )
    except ValueError as exc:
        item, error = None, str(exc)
    if error:
        return templates.TemplateResponse(
            request=request, name="showcase_new.html",
            context={
                "error": error, "current_user": current_user,
                "categories": showcase_service.get_category_options(db), "active_nav": "showcase_manage",
            }, status_code=400,
        )
    add_flash(request, f"资料 {item.title} 已保存", "success")
    return RedirectResponse(url="/showcase/manage", status_code=303)


@router.post("/showcase/manage/delete")
async def showcase_delete_items(request: Request, db: Session = Depends(get_db)):
    if require_login(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)
    payload = await request.json()
    raw_ids = payload.get("ids") if isinstance(payload, dict) else []
    item_ids = []
    for raw_id in raw_ids if isinstance(raw_ids, list) else []:
        try:
            item_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    if not item_ids:
        return JSONResponse({"error": "请至少选择一条资料"}, status_code=400)
    current_user = get_current_user(request, db)
    deleted = showcase_service.delete_items(db, item_ids, current_user.username if current_user else "")
    add_flash(request, f"已删除 {deleted} 条资料", "success")
    return {"ok": True, "deleted": deleted}


def _quotation_response(rows, kind: str):
    if not rows:
        return JSONResponse({"error": "请至少选择一条资料"}, status_code=400)
    try:
        output = build_quote_image(rows) if kind == "image" else build_quote_excel(rows)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    if kind == "image":
        return StreamingResponse(
            output, media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="material-list-{timestamp}.png"'},
        )
    return StreamingResponse(
        output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="material-list-{timestamp}.xlsx"'},
    )


@router.post("/showcase/quotation/image")
async def showcase_quotation_image(request: Request):
    if require_login(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)
    payload = await request.json()
    return _quotation_response(normalize_quote_rows(payload.get("rows") if isinstance(payload, dict) else payload), "image")


@router.post("/showcase/quotation/excel")
async def showcase_quotation_excel(request: Request):
    if require_login(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)
    payload = await request.json()
    return _quotation_response(normalize_quote_rows(payload.get("rows") if isinstance(payload, dict) else payload), "excel")
