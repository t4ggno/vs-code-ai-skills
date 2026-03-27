---
name: rest-api-client
description: Calls HTTP APIs with structured request options, supports seed-user login and token exchange flows, and returns safely truncated responses for debugging protected endpoints.
---

# REST API Client Skill

Use this skill when the agent needs to call a REST API directly instead of guessing how an endpoint behaves.

It is especially useful for:

- Verifying protected endpoints end-to-end.
- Testing login or token exchange flows with seeded users.
- Replaying authenticated requests with bearer tokens or cookie sessions.
- Inspecting JSON or text responses without flooding the chat context.

## Authentication guidance

Prefer **seed/test users** for simulated production flows. This skill supports two lean authentication modes:

- `seed-login`: Signs in first, keeps the session cookies, optionally extracts a token from the login response, and then calls the target endpoint.
- `bearer-env`: Reads a bearer token from an environment variable without exposing the raw token in chat.

For token exchange bodies and request payloads, the script supports these placeholders:

- `{{seed_username}}`
- `{{seed_password}}`
- `{{token}}`
- `{{env:VARIABLE_NAME}}`

## Setup

Make sure the current Python environment has the dependencies from `requirements.txt` installed.

## Usage

Call the script like this:

```bash
python c:/Users/ehrha/.copilot/skills/rest-api-client/call_api.py GET http://localhost:3000/api/health
```

### Protected endpoint with seeded login

```bash
python c:/Users/ehrha/.copilot/skills/rest-api-client/call_api.py GET http://localhost:3000/api/users/me --auth-mode seed-login --login-url http://localhost:3000/api/auth/login --seed-username seeded-admin@example.com --seed-password Passw0rd! --token-json-path accessToken
```

### Password-grant style token exchange with a seeded user

```bash
python c:/Users/ehrha/.copilot/skills/rest-api-client/call_api.py GET http://localhost:3000/api/users/me --auth-mode seed-login --login-url http://localhost:3000/oauth/token --login-content-type form --login-body '{"grant_type":"password","username":"{{seed_username}}","password":"{{seed_password}}","client_id":"{{env:API_CLIENT_ID}}"}' --seed-username seeded-admin@example.com --seed-password Passw0rd! --token-json-path access_token
```

### Reuse an existing bearer token from the environment

```bash
python c:/Users/ehrha/.copilot/skills/rest-api-client/call_api.py POST http://localhost:3000/api/posts --auth-mode bearer-env --auth-env-var API_BEARER_TOKEN --json-body '{"title":"Seeded smoke test"}'
```

## Notes

- Login responses are not echoed back with secrets.
- Sensitive headers like `Authorization` and `Cookie` are redacted in the output.
- Use `--max-body-chars` to cap large responses.
- Use `--insecure` only for local development with self-signed TLS.
