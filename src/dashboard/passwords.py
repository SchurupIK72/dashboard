import base64
import hashlib
import hmac
import secrets

SCHEME = "scrypt"
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
DERIVED_KEY_LENGTH = 32
SALT_LENGTH = 16
MAX_MEMORY_BYTES = 64 * 1024 * 1024
MAX_N = 2**20
MAX_R = 32
MAX_P = 32
MAX_DERIVED_KEY_LENGTH = 64
STORED_PART_COUNT = 6


def hash_password(password: str) -> str:
    """Return a salted scrypt hash of the password in the stored string format."""
    salt = secrets.token_bytes(SALT_LENGTH)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=MAX_MEMORY_BYTES,
        dklen=DERIVED_KEY_LENGTH,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_hash = base64.b64encode(derived).decode("ascii")
    return f"{SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_hash}"


def _parse_parameter(text: str, maximum: int) -> int:
    if not (text.isascii() and text.isdigit()):
        raise ValueError("parameter is not a decimal number")
    value = int(text)
    if value < 1 or value > maximum:
        raise ValueError("parameter is out of range")
    return value


def verify_password(password: str, stored_hash: str) -> bool:
    """Check the password against a stored hash; return False for any malformed hash."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != STORED_PART_COUNT or parts[0] != SCHEME:
            return False
        n = _parse_parameter(parts[1], MAX_N)
        r = _parse_parameter(parts[2], MAX_R)
        p = _parse_parameter(parts[3], MAX_P)
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
        if not salt or not 0 < len(expected) <= MAX_DERIVED_KEY_LENGTH:
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=MAX_MEMORY_BYTES,
            dklen=len(expected),
        )
    except (ValueError, TypeError, OverflowError, MemoryError):
        return False
    return hmac.compare_digest(derived, expected)


DUMMY_PASSWORD_HASH: str = hash_password(secrets.token_urlsafe(32))
