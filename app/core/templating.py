from fastapi.templating import Jinja2Templates

from .config import settings
from .web import get_flashes
from ..utils.formatters import action_label, format_money


templates = Jinja2Templates(directory=str(settings.template_dir))
templates.env.globals.update(
    get_flashes=get_flashes,
    action_label=action_label,
    format_money=format_money,
)
