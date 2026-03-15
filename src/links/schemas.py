from datetime import datetime
from typing import Optional
from pydantic import BaseModel, AnyHttpUrl, field_validator, ConfigDict


class LinkCreate(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, value: Optional[str]):
        if value is None:
            return value

        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "custom_alias может содержать только буквы, цифры, - и _"
            )

        if len(value) < 3 or len(value) > 32:
            raise ValueError("custom_alias должен быть длиной от 3 до 32 символов")

        return value


class LinkUpdate(BaseModel):
    original_url: AnyHttpUrl


class LinkResponse(BaseModel):
    status: str
    data: dict


class LinkStatsResponse(BaseModel):
    original_url: str
    short_code: str
    created_at: datetime
    click_count: int
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]

class LinkSearchItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_url: str
    short_code: str


class LinkSearchResponseSchema(BaseModel):
    data: list[LinkSearchItemSchema]