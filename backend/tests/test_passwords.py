from app.auth.passwords import hash_password, verify_password


def test_hash_and_verify():
    h = hash_password("s3cret")
    assert h != "s3cret" and h.startswith("pbkdf2$")
    assert verify_password("s3cret", h) is True
    assert verify_password("wrong", h) is False


def test_verify_bad_format():
    assert verify_password("x", "not-a-hash") is False
