"""Onboard or offboard a customer tenant with Terraform.

Each customer gets its own Terraform workspace, so one customer's state can never touch another's.

    python -m onboarding.onboard cliente-b --action plan
    python -m onboarding.onboard cliente-b --action apply
    python -m onboarding.onboard cliente-b --action plan-destroy
    python -m onboarding.onboard cliente-b --action destroy

apply and destroy ask you to type the customer name unless --auto-approve is given (CI only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TF_DIR = Path(__file__).resolve().parent.parent / "terraform" / "customer-onboarding"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,30}$")
RESERVED_NAMES = {"default", "dev", "prod", "pro", "trial"}
REQUIRED_ENV = (
    "TF_VAR_subaccount_id",
    "TF_VAR_xsuaa_app_suffix",
    "TF_VAR_admin_user",
)
CREDENTIAL_ENV = (("BTP_USERNAME", "BTP_ENABLE_SSO"), ("CF_USER",))

# Known Terraform or platform messages, mapped to an explanation a support engineer can act on.
KNOWN_ERRORS = (
    ("quota", "The subaccount has no quota left for this service. Free quota in Entitlements."),
    (
        "already exists",
        "A resource with this name already exists outside Terraform. "
        "Pick another customer name, or remove the leftover resource first.",
    ),
    (
        "must be unique",
        "A resource with this name already exists outside Terraform. "
        "Pick another customer name, or remove the leftover resource first.",
    ),
    (
        "role template",
        "The XSUAA role template was not found. Check TF_VAR_xsuaa_app_suffix "
        "against Security > Roles in the cockpit.",
    ),
    ("unauthorized", "Authentication failed. Check the BTP and Cloud Foundry credentials."),
    ("invalid_grant", "Authentication failed. Check the BTP and Cloud Foundry credentials."),
)


class OnboardingError(Exception):
    """A failure with a message meant for the person running the onboarding."""


def validate_customer(name: str) -> None:
    if not NAME_PATTERN.fullmatch(name):
        raise OnboardingError(
            f"Invalid customer name '{name}'. Use 3 to 31 lowercase letters, digits or hyphens, "
            "starting with a letter."
        )
    if name in RESERVED_NAMES:
        raise OnboardingError(f"'{name}' is reserved for the platform itself. Pick another name.")


def check_env(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ) if env is None else env
    missing = [key for key in REQUIRED_ENV if not env.get(key)]
    for options in CREDENTIAL_ENV:
        if not any(env.get(key) for key in options):
            missing.append(" or ".join(options))
    if missing:
        raise OnboardingError("Missing environment variables: " + ", ".join(missing))


def explain_failure(output: str) -> str:
    text = output.lower()
    for needle, message in KNOWN_ERRORS:
        if needle in text:
            return message
    return "Terraform failed. The full output is above."


def terraform(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"\n$ terraform {' '.join(args)}", flush=True)
    result = subprocess.run(
        ["terraform", *args], cwd=TF_DIR, text=True, capture_output=True, check=False
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if check and result.returncode != 0:
        raise OnboardingError(explain_failure(result.stdout + result.stderr))
    return result


def confirm(customer: str, verb: str) -> None:
    answer = input(f"\nType the customer name to {verb} '{customer}': ").strip()
    if answer != customer:
        raise OnboardingError("Confirmation did not match. Nothing was changed.")


def summary(lines: list[str], echo: bool = True) -> None:
    """Print a short result, and add it to the GitHub Actions run summary when running in CI."""
    text = "\n".join(lines)
    if echo:
        print("\n" + text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def select_workspace(customer: str, create: bool) -> None:
    if create:
        terraform("workspace", "select", "-or-create", customer)
        return
    result = terraform("workspace", "select", customer, check=False)
    if result.returncode != 0:
        raise OnboardingError(f"No onboarding found for '{customer}'. Nothing to remove.")


def verify_matches_code(customer: str) -> None:
    """A second plan must show no changes: the platform now matches the code."""
    result = terraform(
        "plan",
        "-input=false",
        "-no-color",
        "-detailed-exitcode",
        f"-var=customer={customer}",
        check=False,
    )
    if result.returncode == 2:
        raise OnboardingError("Applied, but a new plan still shows changes. Check for drift.")
    if result.returncode != 0:
        raise OnboardingError(explain_failure(result.stdout + result.stderr))


def onboard(customer: str, action: str, auto_approve: bool) -> None:
    validate_customer(customer)
    check_env()
    terraform("init", "-input=false", "-no-color")
    select_workspace(customer, create=action in {"plan", "apply"})

    destroying = action in {"plan-destroy", "destroy"}
    plan_args = ["plan", "-input=false", "-no-color", f"-var=customer={customer}", "-out=tfplan"]
    if destroying:
        plan_args.insert(1, "-destroy")
    terraform(*plan_args)

    if action in {"plan", "plan-destroy"}:
        summary([f"## Plan for `{customer}`", "", "Nothing was changed. Review the plan above."])
        return

    if not auto_approve:
        confirm(customer, "remove" if destroying else "onboard")
    terraform("apply", "-input=false", "-no-color", "tfplan")

    if destroying:
        remaining = terraform("state", "list").stdout.strip()
        if remaining:
            raise OnboardingError(f"Resources still in state after destroy:\n{remaining}")
        terraform("workspace", "select", "default")
        terraform("workspace", "delete", customer)
        summary([f"## Offboarded `{customer}`", "", "All resources removed, workspace deleted."])
        return

    verify_matches_code(customer)
    outputs = json.loads(terraform("output", "-json").stdout)
    summary(
        [
            f"## Onboarded `{customer}`",
            "",
            f"- Space: `{outputs['space_name']['value']}`",
            f"- Role collection: `{outputs['role_collection']['value']}`",
            "- Verified: a second plan shows no changes",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Onboard or offboard a customer tenant.")
    parser.add_argument("customer", help="customer name, e.g. cliente-b")
    parser.add_argument(
        "--action",
        choices=["plan", "apply", "plan-destroy", "destroy"],
        default="plan",
    )
    parser.add_argument("--auto-approve", action="store_true", help="skip confirmation (CI)")
    args = parser.parse_args(argv)
    try:
        onboard(args.customer, args.action, args.auto_approve)
    except OnboardingError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        summary([f"## Onboarding failed for `{args.customer}`", "", str(error)], echo=False)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
