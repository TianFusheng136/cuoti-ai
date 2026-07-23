from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InputType = Literal["text", "image", "clipboard"]


class QuestionCreate(BaseModel):
    input_type: InputType
    source_text: str | None = Field(default=None, max_length=50_000)

    @model_validator(mode="after")
    def validate_content(self) -> "QuestionCreate":
        if self.source_text is not None:
            self.source_text = self.source_text.strip()
        if self.input_type == "text" and not self.source_text:
            raise ValueError("文字题目不能为空")
        return self


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_type: str
    relative_path: str
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    width: int
    height: int
    created_at: datetime


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    input_type: InputType
    source_text: str | None
    status: str
    assets: list[AssetResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class QuestionListResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
