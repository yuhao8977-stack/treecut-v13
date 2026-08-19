"""P5+P7: 内容模板引擎（CT01-CT12）。"""

from .definitions import CT01, CT02, TEMPLATES, get_template, list_templates
from .engine import SlotCandidate, TemplateEngine

__all__ = ["CT01", "CT02", "TEMPLATES", "get_template", "list_templates",
           "SlotCandidate", "TemplateEngine"]
