import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MIN_VISIBLE_RANGE = 5
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredImage:
    relative_path: str
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    width: int
    height: int


async def store_question_image(file: UploadFile, uploads_root: Path) -> StoredImage:
    original_filename = Path(file.filename or "题目图片").name
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ImageValidationError("仅支持 JPG、PNG 或 WebP 格式的题目图片。")

    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageValidationError("图片不能超过 15MB，请压缩或裁切后重试。")
    if not content:
        raise ImageValidationError("图片内容为空，请重新选择文件。")

    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            image.verify()
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            sample = image.convert("L")
            sample.thumbnail((512, 512))
            minimum, maximum = sample.getextrema()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageValidationError("文件不是有效的题目图片，请重新选择。") from exc

    if image_format not in FORMAT_DETAILS:
        raise ImageValidationError("仅支持 JPG、PNG 或 WebP 格式的题目图片。")
    if width < 1 or height < 1:
        raise ImageValidationError("图片尺寸无效，请重新选择。")
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageValidationError("图片像素尺寸过大，请压缩到 4000 万像素以内。")
    if maximum - minimum < MIN_VISIBLE_RANGE:
        raise ImageValidationError("图片内容接近空白，请重新截图或选择清晰题目图片。")

    mime_type, canonical_extension = FORMAT_DETAILS[image_format]
    extension_matches = extension == canonical_extension or (
        image_format == "JPEG" and extension == ".jpeg"
    )
    if not extension_matches:
        raise ImageValidationError("图片扩展名与实际格式不一致，请重新保存后上传。")

    now = datetime.now(UTC)
    relative_directory = Path("uploads") / f"{now:%Y}" / f"{now:%m}"
    destination_directory = uploads_root.parent / relative_directory
    destination_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{canonical_extension}"
    destination = destination_directory / filename
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(destination)

    return StoredImage(
        relative_path=(relative_directory / filename).as_posix(),
        original_filename=original_filename,
        mime_type=mime_type,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
    )
