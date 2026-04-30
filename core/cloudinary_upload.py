"""Cloudinary Upload — upload CV PDF lên Cloudinary.

Trả về public URL để lưu vào JOBAPPLICATION.cvSnapUrl
và trigger FANG ingestion pipeline.

Cấu hình:
- CLOUDINARY_UPLOAD_FOLDER: tên folder đích (ttcs, nmaiex, v.v.)
  Cloudinary mặc định upload vào Home folder, nên chỉ cần định folder name
- Đường dẫn thực tế trên Cloudinary sẽ là: ttcs/ hoặc nmaiex/
"""

from __future__ import annotations

import os

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# Đọc từ .env, mặc định là "ttcs" nếu không cấu hình
# Không cần thêm "Home/" vì Cloudinary đã mặc định upload vào Home
_FOLDER = os.getenv("CLOUDINARY_UPLOAD_FOLDER", "ttcs")


def upload_cv_pdf(file_bytes: bytes, filename: str) -> str:
    """Upload file PDF lên Cloudinary.

    Args:
        file_bytes: nội dung file PDF dạng bytes
        filename: tên file gốc (dùng làm public_id hint)

    Returns:
        str: public URL của file đã upload (HTTPS)

    Raises:
        RuntimeError nếu upload thất bại

    Chi tiết:
        - Folder được cấu hình qua CLOUDINARY_UPLOAD_FOLDER trong .env
        - Cloudinary mặc định upload vào Home folder
        - URL sẽ là: https://res.cloudinary.com/.../upload/ttcs/filename.pdf
    """
    # Sanitize filename để làm public_id
    base_name = os.path.splitext(filename)[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)

    result = cloudinary.uploader.upload(
        file_bytes,
        resource_type="raw",  # PDF là raw resource
        folder=_FOLDER,  # "ttcs" or "nmaiex" (không cần thêm Home/)
        public_id=safe_name,
        overwrite=True,  # overwrite nếu upload lại
        use_filename=True,
        unique_filename=False,
    )

    url = result.get("secure_url")
    if not url:
        raise RuntimeError(
            f"Cloudinary upload thất bại, không có secure_url. Result: {result}"
        )
    return url
