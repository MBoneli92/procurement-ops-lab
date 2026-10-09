# Learning Log

Daily record of building **procurement-ops-lab**: what I built, what broke, how I diagnosed it and what I took away. Failures are reproduced on purpose whenever possible, because knowing how a system breaks is most of operating it.

## Progress at a glance

| Day | Date | Topic | Outcome |
|---|---|---|---|
| 1 | Oct 6 | Python service | FastAPI app with suppliers and purchase orders, 11 tests, lint clean |
| 2 | Oct 7 | Cloud Foundry | App running in the `dev` space, deployed first with `cf push`, then as an MTA |
| 3 | Oct 7 | Security | XSUAA with scopes, role templates and role collections; 401, 403 and 503 reproduced |
| 4 | Oct 8 | CI | GitHub Actions with lint, tests, 90% coverage gate and versioned `.mtar` artifact |
| 5 | Oct 9 | CD on SAP BTP | SAP CI/CD service deploying to `dev` on every push through a GitHub webhook |

---

## Day 1 · Oct 6 · Python service

**Built**
- FastAPI service with suppliers and purchase orders, Pydantic models and an approval flow (`DRAFT → SUBMITTED → APPROVED / REJECTED`).
- 11 pytest tests, ruff clean, explored the full flow through Swagger UI.

**Broke on purpose**
- Removed the "blocked supplier" rule from the router. The test caught it immediately: `assert 201 == 422` (the API created an order it should have rejected).

**Fixed**
- `git diff` to see exactly what changed, `git restore` to roll back.

**Takeaways**
- Two kinds of `422`: a blocked supplier is a **business rule** in my router; `quantity: 0` is rejected by **Pydantic** before my code even runs. The error's `loc` field points to the exact field, the same format I will read in Integration Suite message monitoring.
- Reading a failing assertion as *expected vs. observed* is the same reasoning as any incident analysis.

---

## Day 2 · Oct 7 · Cloud Foundry

**Built**
- Installed the cf CLI, the MultiApps plugin and the Cloud MTA Build Tool.
- Deployed with `cf push` (`manifest.yml`), then switched to an MTA (`mta.yaml`, `mbt build`, `cf deploy`).

**Tooling incidents**
- **Homebrew refused an untrusted tap** (`cloudfoundry/tap`). Fixed with `brew trust` and `brew link`. A dependency changed its behavior and broke the setup: a classic DevOps blocker.
- **`bad CPU type in executable`** when installing the MultiApps plugin. The binary was built for Intel and my Mac is Apple Silicon (`arm64`). Fixed by installing Rosetta 2. The same class of problem shows up with Docker images (`amd64` image on an `arm64` host).

**Broke on purpose**
- Typo in the start command (`app.mian`). Staging succeeded, start failed. Diagnosed with `cf events` (`app.crash`) and `cf logs --recent` (`ModuleNotFoundError`).

**Experiment: why cloud apps must be stateless**
- Scaled to two instances (`cf scale -i 2`), created a supplier, then called `GET /suppliers` repeatedly. Sometimes it was there, sometimes not.
- The Cloud Foundry router spreads requests across instances, and each instance keeps its own in-memory data. Logs showed which instance answered (`[APP/PROC/WEB/0]` vs `[APP/PROC/WEB/1]`).
- Lesson: state belongs in a managed service (database, cache), never in the process. That is what makes horizontal scaling and restarts safe.

**Takeaways**
- **Staging failure** = build problem (buildpack, dependencies, Python version). **Start failure** = runtime problem (command, port, missing variable). Knowing which phase failed cuts the diagnosis in half.
- `VCAP_APPLICATION` and `VCAP_SERVICES` are how Cloud Foundry tells the app about itself and its services.
- `cf push` deploys one app; `cf deploy` deploys a package with apps, services and dependencies, which Cloud TMS can transport. Build once, deploy many.

---

## Day 3 · Oct 7 · Security with XSUAA

**Built**
- `xs-security.json` with `Viewer` and `Admin` scopes, role templates and role collections (`ProcurementViewer`, `ProcurementAdmin`).
- Token validation in the app with `sap-xssec`; XSUAA declared as an MTA resource and bound to the app.
- `/me` endpoint to show the caller's identity and scopes.

**Broke on purpose**
- **Binding removed** (`cf unbind-service`): the app answered `503 Auth service not bound`. A redeploy of the same `.mtar` restored the binding, because the package is the source of truth.
- **Tampered token**: `401 Invalid token`; the real reason only appears in the app logs.
- **Technical token** (client credentials) got `403` on `POST`, because the app's `authorities` only grant `Viewer`.

**Takeaways**
- `401` = I don't know who you are. `403` = I know who you are, and you can't do this. `503` = the environment is misconfigured, not the code.
- The chain is **scope → role template → role collection → user**. Developers define the first two; administrators assign the last one.
- A token is a snapshot of permissions at the moment it was issued. A new role collection only takes effect with a new token.

---

## Day 4 · Oct 8 · Continuous integration + cockpit review

**Built**
- GitHub Actions workflow: ruff, pytest with a 90% coverage gate, and `mbt build` producing `procurement-ops-lab_<sha>.mtar` as an artifact.
- Cockpit tour of everything created so far, plus an inventory of the services available in the trial.

**Broke on purpose (on a pull request)**
1. **Lint**: unused import, annotated inline on the pull request; the build job was skipped.
2. **Test**: allowed approving drafts; `gh run view --log-failed` showed `assert 200 == 409`.
3. **Coverage**: untested endpoint; all tests passed, but the 90% gate failed the job.

**Credential incident**
- During a 403 test I hit three different credentials, each with its own lifecycle:

| Error | Credential | Fix |
|---|---|---|
| `invalid_client` | Service key secret (dies when the key is deleted or recreated) | Read the current key and update the secret |
| `401` from the app | XSUAA user token (expires in hours, snapshot of roles) | Request a new token |
| `Please log back in` | cf CLI session token | `cf login` |

**Takeaways**
- CI trusts exit codes: `0` means success, anything else fails the step.
- CI validates and packages; it does not deploy. The app's **Events** in the cockpit proved nothing changed in `dev`.
- A bug blocked on a pull request never reaches the environment. That is the point of CI.

---

## Day 5 · Oct 9 · SAP Continuous Integration and Delivery service

**Built**
- Subscribed to the service and assigned the `CICD Service Administrator` and `CICD Service Developer` role collections.
- Credentials: a repository-scoped, read-only GitHub token; a Cloud Foundry user; a webhook secret.
- Job on the CAP pipeline template with Build and Release (deploy to `dev`). A push to `main` now deploys automatically; version `0.2.1` confirmed through `/health`.

**Broke on purpose**
- **Wrong webhook secret**: no build was triggered. GitHub's *Recent Deliveries* showed the rejected request.
- **Non-existent space**: Build passed, Release failed. The package was fine; the target was wrong.

**How to debug "I pushed and nothing happened"**
1. Check *Recent Deliveries* on the sender side (GitHub).
2. Not sent → webhook configuration (event type, inactive webhook).
3. Sent and rejected → the response explains why (secret, URL).
4. Accepted but no build → service side (branch filter, job turned off).

**Takeaways**
- Subscribing to the service is itself a tenant onboarding: a new tenant, new role collections, logout and login to refresh the token.
- **Known gap:** GitHub Actions tests and the CI/CD service deploys, but nothing links them. A commit with failing tests still reaches `dev`. Options: branch protection, a single gated pipeline, or tests inside the CI/CD service through `.pipeline/config.yml`.
- **Trial limitations:** the CAP template does not run pytest, and deployments use my personal user; a real landscape would use a dedicated technical user.

**Next:** continuous deployment from GitHub Actions with an approval gate, and the Destination service.