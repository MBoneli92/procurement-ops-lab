import pytest

from onboarding import onboard
from onboarding.onboard import OnboardingError, check_env, explain_failure, validate_customer

FULL_ENV = {
    "TF_VAR_subaccount_id": "sub",
    "TF_VAR_xsuaa_app_suffix": "!t1",
    "TF_VAR_admin_user": "user@example.com",
    "BTP_USERNAME": "user@example.com",
    "CF_USER": "user@example.com",
}


@pytest.mark.parametrize("name", ["cliente-a", "acme", "acme-eu-2"])
def test_valid_names(name):
    validate_customer(name)


@pytest.mark.parametrize("name", ["A", "ab", "Cliente-A", "1acme", "acme_eu", "a" * 40, ""])
def test_invalid_names(name):
    with pytest.raises(OnboardingError, match="Invalid customer name"):
        validate_customer(name)


@pytest.mark.parametrize("name", ["dev", "prod", "trial"])
def test_reserved_names(name):
    with pytest.raises(OnboardingError, match="reserved"):
        validate_customer(name)


def test_env_complete():
    check_env(FULL_ENV)


def test_env_sso_instead_of_btp_user():
    env = {k: v for k, v in FULL_ENV.items() if k != "BTP_USERNAME"} | {"BTP_ENABLE_SSO": "true"}
    check_env(env)


def test_env_missing_lists_every_gap():
    with pytest.raises(OnboardingError) as error:
        check_env({"TF_VAR_admin_user": "x"})
    message = str(error.value)
    assert "TF_VAR_subaccount_id" in message
    assert "BTP_USERNAME or BTP_ENABLE_SSO" in message
    assert "CF_USER" in message


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("Error: Quota exceeded for service plan", "quota"),
        ("Error: Space with name already exists", "already exists"),
        ("role template 'Viewer' not found", "TF_VAR_xsuaa_app_suffix"),
        ("Error: No existing workspaces.", "onboarding-bootstrap"),
        ("something unexpected", "full output"),
    ],
)
def test_explain_failure(output, expected):
    assert expected in explain_failure(output)


def test_invalid_name_never_calls_terraform(monkeypatch):
    calls = []
    monkeypatch.setattr(onboard, "terraform", lambda *a, **k: calls.append(a))
    assert onboard.main(["Bad_Name", "--action", "apply"]) == 1
    assert calls == []
