from typing import Any, List
import orjson
from pydantic import BaseModel, Field, validator
from pydantic.schema import date, datetime

from src.utils.functions import date_to_string, datetime_to_string

EXAMPLE_DATETIME = '2022-01-31 23:04:11'


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


class BaseSchema(BaseModel):
    class Config:
        json_loads = orjson.loads
        json_dumps = orjson_dumps
        json_encoders = {
            datetime: lambda dt: datetime_to_string(dt),
            date: lambda d: date_to_string(d)
        }

    @validator('*', pre=True)
    def none_to_empty_string(cls, v):
        if v is None:
            return ''
        return v


class Error(BaseSchema):
    loc: str = Field(..., description='Vị trí lỗi')
    msg: str = Field(..., description='Mã lỗi')
    detail: str = Field(..., description='Mô tả chi tiết')


class ResponseError(BaseSchema):
    data: Any = None
    errors: List[Error] = Field(..., description='Lỗi trả về liên quan validation hoặc call không được')

