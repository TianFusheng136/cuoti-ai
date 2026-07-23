import ctypes
import os
import uuid
from pathlib import Path
from typing import Protocol


class SecretProtectionError(RuntimeError):
    pass


class SecretProtector(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...

    def unprotect(self, ciphertext: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_ubyte]]:
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


class WindowsDpapiProtector:
    """使用当前 Windows 用户范围的 DPAPI 加解密本地密钥。"""

    _UI_FORBIDDEN = 0x1

    def __init__(self) -> None:
        if os.name != "nt":
            raise SecretProtectionError("当前系统不支持 Windows DPAPI。")

    def protect(self, plaintext: bytes) -> bytes:
        input_blob, input_buffer = _blob(plaintext)
        output_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        success = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "AI Error Review Workbench",
            None,
            None,
            None,
            self._UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        _ = input_buffer
        if not success:
            raise SecretProtectionError("API Key 加密失败。")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.pbData)  # type: ignore[attr-defined]

    def unprotect(self, ciphertext: bytes) -> bytes:
        input_blob, input_buffer = _blob(ciphertext)
        output_blob = _DataBlob()
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        success = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            self._UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        _ = input_buffer
        if not success:
            raise SecretProtectionError("API Key 解密失败，可能由其他 Windows 用户创建。")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output_blob.pbData)  # type: ignore[attr-defined]


class SecretStore:
    def __init__(self, root: Path, protector: SecretProtector) -> None:
        self.root = root.resolve()
        self.protector = protector
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, secret: str, reference: str | None = None) -> str:
        safe_reference = reference or f"{uuid.uuid4()}.bin"
        path = self._resolve(safe_reference)
        encrypted = self.protector.protect(secret.encode("utf-8"))
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(encrypted)
        temporary.replace(path)
        return safe_reference

    def read(self, reference: str) -> str:
        encrypted = self._resolve(reference).read_bytes()
        return self.protector.unprotect(encrypted).decode("utf-8")

    def delete(self, reference: str) -> None:
        self._resolve(reference).unlink(missing_ok=True)

    def _resolve(self, reference: str) -> Path:
        path = (self.root / reference).resolve()
        if not path.is_relative_to(self.root) or path.parent != self.root:
            raise SecretProtectionError("密钥文件引用无效。")
        return path


def default_secret_protector() -> SecretProtector:
    return WindowsDpapiProtector()
