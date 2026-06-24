import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import ShowcaseItem
from .audit import log_operation
from .quotation import get_pillow_tools

SHOWCASE_IMAGE_SIZE = (900, 900)


def get_category_options(db: Session):
    return [
        row[0]
        for row in db.query(ShowcaseItem.category)
        .filter(ShowcaseItem.category != None, ShowcaseItem.category != "")
        .distinct().order_by(ShowcaseItem.category.asc()).all()
        if row[0]
    ]


def generate_item_code(db: Session, category: str) -> str:
    category_value = category.strip() or "未分类"
    count = db.query(ShowcaseItem).filter(ShowcaseItem.category == category_value).count()
    return f"{category_value}-{count + 1:03d}"


def save_upload(image_file: UploadFile | None):
    if image_file is None or not image_file.filename:
        return ""
    suffix = Path(image_file.filename).suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        raise ValueError("只支持 jpg、png、webp、gif 格式图片")
    try:
        Image, _, _, ImageOps = get_pillow_tools()
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    target = settings.upload_dir / filename
    try:
        image_file.file.seek(0)
        with Image.open(image_file.file) as source:
            source = ImageOps.exif_transpose(source)
            if source.mode in ("RGBA", "LA") or (source.mode == "P" and "transparency" in source.info):
                rgba = source.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.getchannel("A"))
                source = background
            else:
                source = source.convert("RGB")
            resized = ImageOps.fit(source, SHOWCASE_IMAGE_SIZE, method=Image.Resampling.LANCZOS)
            resized.save(target, format="JPEG", quality=88, optimize=True)
    except PermissionError as exc:
        raise ValueError("上传目录没有写入权限，请联系管理员修复 app/static/uploads 权限") from exc
    except Exception as exc:
        raise ValueError("图片处理失败，请确认文件是有效图片") from exc
    return f"/static/uploads/{filename}"


def list_public_items(db: Session, category: str = "", query_text: str = ""):
    query = db.query(ShowcaseItem).filter(ShowcaseItem.is_visible == True)
    if category.strip():
        query = query.filter(ShowcaseItem.category == category.strip())
    if query_text.strip():
        query = query.filter(ShowcaseItem.title.like(f"%{query_text.strip()}%"))
    items = query.order_by(ShowcaseItem.category.asc(), ShowcaseItem.item_code.asc(), ShowcaseItem.id.asc()).all()
    categories = db.query(ShowcaseItem.category).filter(
        ShowcaseItem.is_visible == True
    ).distinct().order_by(ShowcaseItem.category.asc()).all()
    return items, [row[0] for row in categories if row[0]]


def list_manage_items(db: Session, category: str = ""):
    query = db.query(ShowcaseItem)
    if category.strip():
        query = query.filter(ShowcaseItem.category == category.strip())
    return query.order_by(ShowcaseItem.category.asc(), ShowcaseItem.item_code.asc(), ShowcaseItem.id.asc()).all()


def create_item(
    db: Session,
    title: str,
    category: str,
    image_file: UploadFile | None,
    description: str,
    is_visible: bool,
):
    if not title.strip():
        return None, "标题不能为空"
    uploaded_url = save_upload(image_file)
    category_value = category.strip() or "未分类"
    item = ShowcaseItem(
        title=title.strip(), item_code=generate_item_code(db, category_value),
        category=category_value, image_url=uploaded_url,
        description=description.strip(), is_visible=is_visible,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, ""


def delete_items(db: Session, item_ids: list[int], operator: str):
    unique_ids = list(dict.fromkeys(item_ids))[:100]
    if not unique_ids:
        return 0
    items = db.query(ShowcaseItem).filter(ShowcaseItem.id.in_(unique_ids)).all()
    for item in items:
        log_operation(db, "showcase", item.id, "delete_showcase", "item", item.title, "deleted", operator)
        db.delete(item)
    db.commit()
    return len(items)
