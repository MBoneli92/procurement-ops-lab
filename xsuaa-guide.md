# XSUAA in practice: tokens, scopes and role collections

Guide for the `procurement-ops-lab` project: testing authentication on `procurement-api` in the BTP trial from the terminal.

---

## 1. Concepts

| Piece | What it is | Where it lives |
|---|---|---|
| **XSUAA** | BTP's authorization service. Issues JWTs and stores scopes, roles and role collections. | `procurement-xsuaa` instance in the subaccount |
| **xs-security.json** | Defines the app's scopes (`Viewer`, `Admin`), role templates and role collections. | Repository, packaged into the `.mtar` |
| **Scope** | Atomic permission the code checks (`Missing scope: Admin`). | Inside the token |
| **Role collection** | A group of roles an admin assigns to users (`ProcurementAdmin`). | Cockpit > Security |
| **Binding** | XSUAA credentials injected into the app through `VCAP_SERVICES`. The app uses them to validate tokens. | App on Cloud Foundry |
| **Service key** | XSUAA credentials for use **outside** CF (you, a script, an integration). | Service instance |
| **JWT** | Signed token carrying identity and scopes. A snapshot of permissions at the moment it was issued. | `Authorization: Bearer ...` header |

Flow in short: a client asks XSUAA for a token, gets a JWT, sends it to the app; the app validates the signature using its binding and checks that the required scope is in the token.

---

## 2. Prerequisites

- `cf login` done, targeting the `dev` space
- `procurement-api` deployed via MTA and bound to `procurement-xsuaa`
- Health endpoint responding: `curl $API/health`

---

## 3. Create the service key

```bash
cf create-service-key procurement-xsuaa lab-key
cf service-key procurement-xsuaa lab-key
```

- The first command only creates the key and replies `OK`; it prints nothing else.
- The second prints a JSON. You need **three fields** from it: `clientid`, `clientsecret` and `url`.
- The `apiurl` field is **not** your app; it's XSUAA's admin API. Ignore it.

List existing keys: `cf service-keys procurement-xsuaa`

---

## 4. Export the variables

```bash
export CLIENTID='<clientid>'
export CLIENTSECRET='<clientsecret>'
export UAA_URL='<service key url>'
export API='https://<your-app-route>'
```

- `export` stores the value in an environment variable **for the current terminal tab**. Nothing is sent anywhere. Close the tab or shut down the laptop and it's gone.
- **Always single quotes.** The `clientid` contains `!` and the secret often contains `$`. Inside double quotes zsh interprets them: `!` triggers `event not found`, and `$abc` expands to an empty variable, silently truncating the secret.
- `API` is **your app's** route (get it from `cf mta procurement-ops-lab` or `cf app procurement-api`), no trailing slash.
- Paste only the command, never the prompt (`(.venv) matheus@... %`), or you'll get a `parse error`.

Check: `echo $CLIENTID` (must print in full, including the `!`). Don't echo the secret.

---

## 5. App token (client_credentials)

```bash
TOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=client_credentials \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

Piece by piece:

- `TOKEN=$( ... )`: runs what's inside and stores its output in `TOKEN`. The name is your choice; the token type is decided by `grant_type`.
- `curl -s`: HTTP request in silent mode (no progress bar polluting the variable).
- `-u "$CLIENTID:$CLIENTSECRET"`: Basic auth. The app identifies itself to XSUAA. Double quotes here because the shell needs to expand the variables.
- `"$UAA_URL/oauth/token"`: the token endpoint.
- `-d grant_type=client_credentials`: POST body. Requests a token **for the app itself**, no human user involved.
- `| python3 -c ...`: XSUAA returns JSON; Python extracts just the `access_token` field.
- `\`: the command continues on the next line.

No output means success. Check: `echo ${TOKEN:0:20}` should print `eyJ...`.

---

## 6. Call the app with the app token

```bash
curl -s -H "Authorization: Bearer $TOKEN" $API/me
curl -s -H "Authorization: Bearer $TOKEN" $API/suppliers
curl -s -i -H "Authorization: Bearer $TOKEN" -X POST $API/suppliers \
  -H "Content-Type: application/json" -d '{"name":"Acme","country":"BR"}'
```

- `-H`: adds a header. `Authorization: Bearer <token>` is the standard way to send a JWT.
- `/me`: shows what the app read from the token. First diagnostic tool.
- `-i`: includes response headers, including the status line (`HTTP/2 201`, `403`).
- `-X POST`: sets the method explicitly.
- `Content-Type: application/json`: without it FastAPI returns 422.
- `-d '{...}'`: JSON body, single-quoted on the outside.

**Expected result:** `403 Missing scope: Admin` on the POST. App tokens don't receive role collections; their scopes only come from `authorities` in `xs-security.json`. This is authorization working as designed.

---

## 7. User token (password grant)

```bash
read -s PASS
UTOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=password -d username='<your-btp-email>' --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $UTOKEN" $API/me
```

- `read -s PASS`: reads the password without echoing it and without writing it to zsh history. It looks frozen; it's waiting for you to type and hit Enter.
- `grant_type=password`: requests a token **on behalf of a person**. Client ID and secret still go along (the app asks on the user's behalf).
- `--data-urlencode`: encodes the password so `&`, `+`, `=` or `%` don't break the request body.
- `UTOKEN`: U for user. A naming convention to avoid mixing it up with the app `TOKEN`.

**Expected before assigning a role:** `/me` shows your email and `scopes: []`; `GET /suppliers` returns `403 Missing scope: Viewer`.

Caveat: the password grant is legacy and only works because the trial uses SAP ID Service as the IdP. With a corporate IdP, SSO or MFA, the path is browser login through the approuter.

---

## 8. Assign the role collection

Cockpit > **trial** subaccount (not the app) > **Security > Users** > your user (Identity Provider: *Default identity provider*) > Role Collections section > **`...`** > **Assign Role Collection** > `ProcurementAdmin`.

Notes:

- `Subaccount Administrator` administers BTP; it does **not** grant scopes in your app.
- If `ProcurementAdmin` isn't listed, check Security > Role Collections; it should be declared in `xs-security.json`.

Then, in the terminal:

```bash
# old token: still no scopes
curl -s -H "Authorization: Bearer $UTOKEN" $API/me

# new token: repeat step 7 (no need for read if you're in the same tab)
UTOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=password -d username='<your-btp-email>' --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $UTOKEN" $API/me

# read and write
curl -s -i -H "Authorization: Bearer $UTOKEN" $API/suppliers
curl -s -i -H "Authorization: Bearer $UTOKEN" -X POST $API/suppliers \
  -H "Content-Type: application/json" -d '{"name":"Acme","country":"BR"}'

unset PASS
```

**Expected result:** old token has no scopes; new token has `Admin` and `Viewer`; GET returns 200; POST returns 201.

**Lesson:** a token is a snapshot. A role assigned after issuance only shows up in a new token.

---

## 9. Look inside the token

```bash
echo $UTOKEN | cut -d. -f2 | base64 -d 2>/dev/null; echo
```

A JWT has three dot-separated parts (header, payload, signature). This decodes the payload. Look for `scope`, `user_name`, `email`, `grant_type` and `exp` (expiry as epoch). App tokens have no `user_name` or `email`.

Pretty-print app responses: `... | python3 -m json.tool`

---

## 10. Runbook: failures and diagnosis

| Symptom | Likely cause | Diagnosis | Fix |
|---|---|---|---|
| `KeyError: 'access_token'` | XSUAA returned an error (wrong user, password or secret, leftover placeholder) | Run the token curl **without** the pipe to see the raw response | Fix the credential; `read -s PASS` again |
| `zsh: event not found` | `!` inside double quotes | Check the quotes in the export | Use single quotes |
| `zsh: parse error near ...` | Prompt pasted along with the command | Check the start of the pasted line | Paste only the command |
| `401` | Token missing, empty or expired | `echo ${UTOKEN:0:20}` | Get a new token |
| `401 Invalid token` | Signature mismatch (tampered token or from another XSUAA) | `cf logs procurement-api --recent \| grep -i token` | New token from the right XSUAA |
| `403 Missing scope` with a user token | Role collection not assigned, or token issued before assignment | `/me` or decode the JWT | Assign the role; get a new token (logout/login in the browser) |
| `403 Missing scope` with an app token | Role collections don't apply to client_credentials | `grant_type` in the payload | Use a user token, or `authorities` in `xs-security.json` |
| `403` while being Subaccount Administrator | BTP admin is not app admin | User's role collections | Assign the app's role collection |
| `503 Auth service not bound` | Binding removed; app can't validate tokens | `cf services`; log shows `No xsuaa binding found` | `cf deploy` the production `.mtar` (check the version with `cf mtas`) |

---

## 11. Hygiene

- `unset PASS` when done (or close the tab).
- Service keys don't expire. If you won't use it: `cf delete-service-key procurement-xsuaa lab-key -f`.
- **Never** paste a `clientsecret` into a versioned file, chat or screenshot. If it leaks: delete the key and create a new one (the old secret dies immediately).
- **Never** set `AUTH_MODE=local` on Cloud Foundry; it's a full authentication bypass.

---

## 12. Session shortcut

`lab-env.sh` at the project root (add it to `.gitignore` **before** creating it):

```bash
export CLIENTID='<clientid>'
export CLIENTSECRET='<clientsecret>'
export UAA_URL='<url>'
export API='https://<your-app-route>'

read -s "PASS?BTP password: "
echo
export UTOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=password -d username='<your-btp-email>' --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
unset PASS
echo "UTOKEN: ${UTOKEN:0:20}..."
```

```bash
echo "lab-env.sh" >> .gitignore
source lab-env.sh
```

It must be `source`: running it as `./lab-env.sh` makes the variables die with the script instead of reaching your terminal.
