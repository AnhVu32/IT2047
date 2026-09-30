from typing import Any, Dict, List

from fastapi import status

from src.utils.error_messages import MESSAGE_STATUS


class ExceptionHandle(Exception):
    def __init__(
        self,
        errors: List[Dict[str, str]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        self.status_code = status_code
        self.data: Any = data
        self.errors: List[Dict] = errors

    def get_message_detail(self):
        result = []
        if self.errors:
            for temp in self.errors:
                if not temp.get("detail"):
                    temp.update({"detail": MESSAGE_STATUS.get(temp.get("msg"))})
                    result.append(temp)
                else:
                    result.append(temp)
        return result
