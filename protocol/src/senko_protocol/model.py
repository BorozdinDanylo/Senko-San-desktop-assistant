from .enum import Version, DataType
from pydantic import BaseModel, PositiveInt


class Header(BaseModel):
    version: Version
    type: DataType
    body_length: PositiveInt


class Request(BaseModel):
    header: Header
    body: bytes


class ResponseBody(BaseModel):
    status_code: int
    message: str


class Response(BaseModel):
    header: Header
    body: ResponseBody

