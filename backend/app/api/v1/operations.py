from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException, Request

Result = TypeVar("Result")


def single_model_operation(
    operation: str,
) -> Callable[[Callable[..., Awaitable[Result]]], Callable[..., Awaitable[Result]]]:
    """Prevent duplicate paid model calls in this single-process local application."""

    def decorate(
        function: Callable[..., Awaitable[Result]],
    ) -> Callable[..., Awaitable[Result]]:
        @wraps(function)
        async def guarded(*args: Any, **kwargs: Any) -> Result:
            request = kwargs.get("request")
            question_id = kwargs.get("question_id")
            if not isinstance(request, Request) or not isinstance(question_id, str):
                return await function(*args, **kwargs)
            key = (operation, question_id)
            active: set[tuple[str, str]] = request.app.state.active_model_operations
            if key in active:
                raise HTTPException(
                    status_code=409,
                    detail="相同操作正在进行，请等待完成后再试。",
                )
            active.add(key)
            try:
                return await function(*args, **kwargs)
            finally:
                active.discard(key)

        return guarded

    return decorate
