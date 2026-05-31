from collections.abc import Awaitable, Callable

from app.domain.models import Node
from app.services.handlers.base import ExecutionContext, HandlerOutcome
from app.services.handlers.call_service import handle_call_service
from app.services.handlers.exit import handle_exit
from app.services.handlers.if_equals import handle_if_equals
from app.services.handlers.if_file_exists import handle_if_file_exists
from app.services.handlers.print import handle_print
from app.services.handlers.read_file import handle_read_file
from app.services.handlers.set_variable import handle_set_variable

HandlerFn = Callable[[Node, ExecutionContext], Awaitable[HandlerOutcome]]

HANDLERS: dict[str, HandlerFn] = {
    "set_variable": handle_set_variable,
    "call_service": handle_call_service,
    "read_file": handle_read_file,
    "print": handle_print,
    "if_equals": handle_if_equals,
    "if_file_exists": handle_if_file_exists,
    "exit": handle_exit,
}
