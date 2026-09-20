from app.auth.passwords import hash_password
from app.auth.users import User, UserStore


def test_authenticate():
    s = UserStore({"admin": (hash_password("pw"), "admin")})
    assert s.authenticate("admin", "pw") == User("admin", "admin")
    assert s.authenticate("admin", "bad") is None
    assert s.authenticate("ghost", "pw") is None


def test_from_env():
    assert UserStore.from_env({}) is None
    assert UserStore.from_env({"ARGUS_JWT_SECRET": "x"}) is None  # aucun mot de passe
    s = UserStore.from_env({"ARGUS_JWT_SECRET": "x",
                            "ARGUS_ADMIN_PASSWORD": "pw", "ARGUS_HSE_PASSWORD": "pw2"})
    assert s.authenticate("admin", "pw").role == "admin"
    assert s.authenticate("hse", "pw2").role == "hse"
