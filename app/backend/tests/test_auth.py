from __future__ import annotations

import httpx
import jwt
import pytest
import respx

from tests.conftest import CLIENT_ID, OTHER_TENANT, TENANT, TokenFactory
from vanimo.auth.entra import AuthError, JwksCache, TokenValidator
from vanimo.config import Settings


@pytest.fixture
async def validator(unit_settings: Settings, graph_mock: respx.MockRouter) -> TokenValidator:
    http = httpx.AsyncClient()
    return TokenValidator(unit_settings, JwksCache(unit_settings.entra_jwks_url, http))


async def test_valid_token(validator: TokenValidator, make_token: TokenFactory) -> None:
    token = make_token(oid="33333333-3333-3333-3333-333333333333", roles=("Vanimo.Admin", "Other.Role"))
    p = await validator.validate(token)
    assert p.entra_tenant_id == TENANT
    assert p.entra_oid == "33333333-3333-3333-3333-333333333333"
    assert p.roles == {"Vanimo.Admin"}  # unknown roles are dropped
    assert p.is_admin
    assert "access_token" not in repr(p) and token not in repr(p)


async def test_app_id_uri_audience_accepted(validator: TokenValidator, make_token: TokenFactory) -> None:
    await validator.validate(make_token(aud=f"api://{CLIENT_ID}"))


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"aud": "some-other-api"}, "invalid_token"),
        ({"exp_in": -3600}, "token_expired"),
        ({"scp": "User.Read"}, "missing_scope"),
        ({"scp": ""}, "missing_scope"),
        ({"roles": ()}, "not_assigned"),
        ({"roles": ("Something.Else",)}, "not_assigned"),
        ({"extra": {"ver": "1.0"}}, "unsupported_token_version"),
    ],
)
async def test_rejections(validator: TokenValidator, make_token: TokenFactory, kwargs: dict, code: str) -> None:
    with pytest.raises(AuthError) as exc:
        await validator.validate(make_token(**kwargs))
    assert exc.value.code == code


async def test_other_tenant_rejected(validator: TokenValidator, make_token: TokenFactory) -> None:
    # Signed with a trusted key but issued for another tenant: the issuer check fails first.
    with pytest.raises(AuthError) as exc:
        await validator.validate(make_token(tid=OTHER_TENANT))
    assert exc.value.code in ("invalid_token", "wrong_tenant")


async def test_tid_mismatch_with_correct_issuer(validator: TokenValidator, make_token: TokenFactory) -> None:
    with pytest.raises(AuthError) as exc:
        await validator.validate(make_token(extra={"tid": OTHER_TENANT}))
    assert exc.value.code == "wrong_tenant"


async def test_hs256_and_none_rejected(validator: TokenValidator) -> None:
    forged = jwt.encode(
        {"tid": TENANT}, "a-forged-shared-secret-of-32-bytes!!", algorithm="HS256", headers={"kid": "test-key-1"}
    )
    with pytest.raises(AuthError, match="unsupported_token_alg"):
        await validator.validate(forged)
    unsigned = jwt.encode({"tid": TENANT}, None, algorithm="none")
    with pytest.raises(AuthError):
        await validator.validate(unsigned)


async def test_garbage_token(validator: TokenValidator) -> None:
    with pytest.raises(AuthError, match="malformed_token"):
        await validator.validate("not-a-jwt")


async def test_unknown_kid_refetches_once_then_rejects(
    validator: TokenValidator, make_token: TokenFactory, graph_mock: respx.MockRouter
) -> None:
    await validator.validate(make_token())  # primes the cache (1 fetch)
    with pytest.raises(AuthError, match="unknown_signing_key"):
        await validator.validate(make_token(kid="rotated-key"))
    with pytest.raises(AuthError, match="unknown_signing_key"):
        await validator.validate(make_token(kid="rotated-key"))
    jwks_route = graph_mock.routes[0]
    assert jwks_route.call_count == 1  # rate-limited: no refetch storm on bad kids


async def test_jwks_outage_is_503(unit_settings: Settings, make_token: TokenFactory) -> None:
    with respx.mock() as router:
        router.get(unit_settings.entra_jwks_url).mock(return_value=httpx.Response(500))
        v = TokenValidator(unit_settings, JwksCache(unit_settings.entra_jwks_url, httpx.AsyncClient()))
        with pytest.raises(AuthError) as exc:
            await v.validate(make_token())
    assert exc.value.status == 503


async def test_other_client_app_rejected(validator: TokenValidator, make_token: TokenFactory) -> None:
    # A different app in the tenant holding `access_as_user` must not ride on Vanimo's Graph rights.
    with pytest.raises(AuthError) as exc:
        await validator.validate(make_token(extra={"azp": "33333333-3333-3333-3333-333333333333"}))
    assert exc.value.code == "unauthorized_client"


async def test_key_rotation_refetches_after_min_interval(
    validator: TokenValidator, make_token: TokenFactory, graph_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vanimo.auth import entra

    now = [1000.0]
    monkeypatch.setattr(entra.time, "monotonic", lambda: now[0])
    await validator.validate(make_token())
    now[0] += 61  # past the 60 s minimum refresh interval
    with pytest.raises(AuthError, match="unknown_signing_key"):
        await validator.validate(make_token(kid="rotated-key"))
    assert graph_mock.routes[0].call_count == 2


async def test_stale_keys_survive_a_jwks_outage(
    unit_settings: Settings, make_token: TokenFactory, jwks: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vanimo.auth import entra

    now = [1000.0]
    monkeypatch.setattr(entra.time, "monotonic", lambda: now[0])
    with respx.mock() as router:
        route = router.get(unit_settings.entra_jwks_url).mock(
            side_effect=[httpx.Response(200, json=jwks), httpx.Response(503)]
        )
        v = TokenValidator(unit_settings, JwksCache(unit_settings.entra_jwks_url, httpx.AsyncClient()))
        await v.validate(make_token())
        now[0] += 7200  # cache TTL expired; the refresh fails but the known key keeps working
        for _ in range(5):  # and failed refreshes are rate-limited too: no fetch per request
            await v.validate(make_token())
    assert route.call_count == 2


async def test_obo_error_mapping(unit_settings: Settings) -> None:
    from vanimo.auth.entra import Principal
    from vanimo.auth.obo import ConsentRequired, OboClient

    class FakeMsal:
        def __init__(self, result: dict) -> None:
            self.result = result

        def acquire_token_on_behalf_of(self, user_assertion: str, scopes: list[str]) -> dict:
            assert scopes == ["https://graph.microsoft.com/.default"]
            return self.result

    p = Principal("t", "o", frozenset({"Vanimo.User"}), frozenset({"access_as_user"}), access_token="tok")
    obo = OboClient(unit_settings, "secret")
    obo._app = FakeMsal({"access_token": "graph"})  # type: ignore[assignment]
    assert await obo.graph_token(p) == "graph"
    obo._app = FakeMsal({"error": "invalid_grant"})  # type: ignore[assignment]
    with pytest.raises(ConsentRequired):
        await obo.graph_token(p)
    obo._app = FakeMsal({"error": "temporarily_unavailable"})  # type: ignore[assignment]
    with pytest.raises(AuthError) as exc:
        await obo.graph_token(p)
    assert exc.value.code == "obo_failed" and exc.value.status == 502


async def test_superadmin_is_never_taken_from_entra(validator: TokenValidator, make_token: TokenFactory) -> None:
    p = await validator.validate(make_token(roles=("Vanimo.SuperAdmin", "Vanimo.User")))
    assert p.roles == {"Vanimo.User"} and not p.is_superadmin and not p.is_admin
