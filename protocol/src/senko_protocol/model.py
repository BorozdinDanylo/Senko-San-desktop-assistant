from .enum import Version, DataType
from pydantic import BaseModel, PositiveInt, Field
import uuid


def model_to_bytes(model: BaseModel) -> bytes:
    return model.model_dump_json().encode()


class Header(BaseModel):
    version: Version
    type: DataType
    body_length: PositiveInt
    request_id: uuid.UUID | None = Field(default=None)


class Request(BaseModel):
    header: Header
    body: bytes


class ResponseBody(BaseModel):
    status_code: int
    message: str


class Response(BaseModel):
    header: Header
    body: ResponseBody

