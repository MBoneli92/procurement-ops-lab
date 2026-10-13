# Runbook

Known failure modes of procurement-ops-lab: how they show up, where to look and how to fix them. Every case here was reproduced on purpose in the SAP BTP trial.

**Format:** symptom → where to look → root cause → fix → prevention.

## Quick triage

| Symptom | First place to look | Most likely case |
|---|---|---|
| App crashes right after deploy | `cf events` / cockpit **Events** | [RB-001](#rb-001-app-crashes-on-start) |
| `503 Auth service not bound` | `cf services`, app **Service Bindings** | [RB-002](#rb-002-xsuaa-binding-missing) |
| `403 Missing scope` for a user who "has the role" | `/me`, **Security > Users** | [RB-003](#rb-003-403-although-the-user-has-the-role) |
| Pushed to `main`, no build started | GitHub **Recent Deliveries** | [RB-004](#rb-004-push-did-not-trigger-a-build) |
| `502` from `/purchase-orders/{id}/converted` | App logs, **Connectivity > Destinations** | [RB-005](#rb-005-destination-with-a-wrong-url) |

---

## RB-001: App crashes on start

**Symptom:** deploy finishes, the app never becomes healthy and Cloud Foundry keeps restarting it.

**Where to look**
- `cf events procurement-api` or cockpit app **Events**: `app.crash` with a non-zero exit code.
- `cf logs procurement-api --recent`: the Python traceback.

**Root cause (reproduced):** typo in the start command (`uvicorn app.mian:app`), so Python raised `ModuleNotFoundError`.

**Fix:** correct the command in `mta.yaml` and redeploy.

**Prevention:** staging and start are different phases. Staging failures point to the build (buildpack, dependencies, Python version); start failures point to runtime (command, port, missing variables).

---

## RB-002: XSUAA binding missing

**Symptom:** every protected endpoint returns `503 Auth service not bound`. `/health` is still fine.

**Where to look**
- `cf services`: the `procurement-xsuaa` row has no bound apps.
- Cockpit: app **Service Bindings** is empty; app logs show `No xsuaa binding found in VCAP_SERVICES`.

**Root cause (reproduced):** the binding was removed by hand (`cf unbind-service`).

**Fix:** redeploy the same `.mtar`. The MTA declares the binding, so the deploy restores it. A manual `cf bind-service` also works, followed by `cf restage`.

**Prevention:** declare every service in `mta.yaml`; treat manual changes as drift.

---

## RB-003: 403 although the user has the role

**Symptom:** `403 Missing scope: Admin` for a user who says the role collection is assigned.

**Where to look, in order**
1. `GET /me` with the same token: which scopes did the token actually carry?
2. Cockpit **Security > Users** > user: is `ProcurementAdmin` assigned?
3. Token age: was the token issued before the assignment?

**Root cause (reproduced):** the role collection was assigned after the token was issued. A token is a snapshot of permissions.

**Fix:** request a new token (or log out and log in).

**Related credential errors**

| Error | Credential | Fix |
|---|---|---|
| `invalid_client` | Service key secret (changes when the key is recreated) | Read the current key |
| `401` from the app | XSUAA token (expired or tampered) | New token |
| `Please log back in` | cf CLI session | `cf login` |

---

## RB-004: Push did not trigger a build

**Symptom:** a commit reached `main`, but the SAP CI/CD service started no build.

**Where to look:** GitHub > Settings > Webhooks > **Recent Deliveries**.

| What you see | Meaning |
|---|---|
| No delivery | Webhook inactive or not subscribed to push events |
| Delivery with an error response | Wrong payload URL or wrong secret; the response body says which |
| `2xx` but no build | Service side: job branch filter or job turned off |

**Root cause (reproduced):** webhook secret in GitHub did not match the one in the CI/CD service.

**Fix:** generate a new secret in the CI/CD service, update the webhook in GitHub, then **Redeliver** the failed delivery.

---

## RB-005: Destination with a wrong URL

**Symptom:** `GET /purchase-orders/{id}/converted?currency=BRL` returns `502`. Everything else works.

**Where to look**
1. Response `detail`: it names the destination and the URL that failed.
2. App logs (`cf logs procurement-api --recent`): a `WARNING app.fx` line with the full URL and the underlying error.
3. Cockpit **Connectivity > Destinations** > `fx-rates`: the configured URL; use **Check Connection**.

**Variants (reproduced)**

| Wrong value | What the app returns | Check Connection |
|---|---|---|
| Host that does not exist | `502 Destination 'fx-rates' unreachable (...): ConnectError` | Fails |
| Right host, wrong base path | `502 Destination 'fx-rates' returned HTTP 404 for ...` | May still pass, because it only checks that the host answers |
| Destination renamed or deleted | `502 Destination 'fx-rates' not found in the subaccount` | Not applicable |
| Destination service not bound | `503 Destination service not bound` | Not applicable |

**Root cause:** the URL of an external system lives in the destination, not in the code, so a configuration change in the cockpit can break the integration without any deploy.

**Fix:** correct the URL in the destination. No restart or redeploy is needed: the app reads the destination on every call.

**Prevention:** after any destination change, run Check Connection **and** call the endpoint that uses it; Check Connection alone does not catch a wrong path.

---

## RB-006: HealthCheckFailed alert

**Symptom:** an email from SAP Alert Notification with subject `<target> is down`, and a red run of the **Health check** workflow in GitHub Actions.

**Where to look**
1. The email body: which URL failed and why (`HTTP 503`, `HTTP 404`, timeout). The `run_url` tag links to the workflow run.
2. GitHub > Actions > **Health check** > the run > **Summary**: one row per target, UP or DOWN, with the detail.
3. `cf app procurement-api` in the target space: `requested state` and the instance state.
4. `cf logs procurement-api --recent`: JSON lines from `procurement.access`; filter by `request_id` to follow one request.

| Detail in the alert | Likely cause | First action |
|---|---|---|
| `HTTP 404` with `Requested route ... does not exist` | App stopped or route removed | `cf app procurement-api`; `cf start procurement-api` if it was stopped |
| `HTTP 502` or `HTTP 503` | App crashing or starting | `cf events procurement-api`, then RB-001 |
| `HTTP 0 ... timed out` | Platform or network problem | Check SAP Trust Center status; retry the workflow |
| `HTTP 200 but body=...` | App up but reporting unhealthy | Read the body, then the app logs |

**Root cause (reproduced):** `cf stop procurement-api` in space `dev`. The next run marked `procurement-api-dev` DOWN after 3 attempts and the email arrived. `cf start` turned the next run green.

**Fix:** depends on the row above. After the fix, run the workflow manually (**Run workflow**) to confirm it is green.

**Prevention and tuning**
- 3 attempts 5 seconds apart before alerting, so one slow answer is not an incident.
- The workflow alerts on every failed run. If the alert repeats while you work on it, use **Snooze by** on the subscription in Alert Notification.
- In a trial account the platform can stop apps by itself; an alert after that is the check doing its job, not a false alarm.
- The service key `github-actions` is long-lived. Rotate it by creating a new key, updating the three `ALERT_*` secrets, then deleting the old key.

---

## RB-007: Ariba order did not become a purchase order

**Symptom:** `ariba_sim.py` prints an HTTP error instead of `HTTP 200` with a cXML `Status code="200"`, or the order is missing from `GET /purchase-orders`.

**Where to look, in this order**
1. What the sender got: the HTTP code and body printed by `ariba_sim.py`.
2. Integration Suite > **Monitor** > **Integrations and APIs** > **Monitor Message Processing**: filter by the custom header `AribaOrderID`. Status `Failed` shows the error of the step that broke.
3. With log level `Trace` on the iFlow (lasts 10 minutes), **Message Content** shows the payload before and after each step.
4. `cf logs procurement-api --recent`: the JSON line `purchase order created` with `order_id`, or the `procurement.access` line with the 4xx status.

| What you see | Meaning | Fix |
|---|---|---|
| `ariba_sim.py`: HTTP 401 | Wrong or missing credentials of the `ariba-sim` key | Copy `clientid`, `clientsecret` and `tokenurl` again from the key |
| `ariba_sim.py`: HTTP 403 | The key's instance lacks role `ESBMessaging.send`, or the sender adapter expects another role | Recreate the instance with the role, or fix the adapter |
| `ariba_sim.py`: HTTP 404 | Wrong path, or the iFlow is not deployed | Endpoint is `<url>/http/ariba/orders`; check **Manage Integration Content** shows `Started` |
| Monitor: script error `cXML OrderRequest needs ...` | Payload without `orderID` or numeric `SupplierID` | Fix the sender; the mapping rejects it on purpose |
| Monitor: `SAXParseException` in script 1 | Malformed XML | The sender must send well-formed cXML |
| Monitor: HTTP 401 from the receiver | Security Material `procurement-api-oauth` has a wrong secret or token URL | Update the credential, then **Deploy** it |
| Monitor: HTTP 403 `Missing scope: one of Admin, OrderIntake` | `OrderIntake` not in the token: `xs-security.json` not deployed yet, or a key from another XSUAA instance | Deploy the app, then create a new token (tokens keep the scopes they were issued with) |
| Monitor: HTTP 422 `Supplier does not exist` | The app restarted and lost its in-memory data, or a wrong `SupplierID` | Create the supplier again with an Admin token |
