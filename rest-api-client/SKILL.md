---
name: rest-api-client
description: Calls HTTP APIs with structured headers, params, bodies, and optional seed-user authentication flows. Use to verify real endpoint behavior or protected API flows. Do not use it for browser-only interactions, load testing, or uncontrolled secret exposure.
argument-hint: <method url> [auth mode, login flow, body, headers]
---

# REST API Client

1. Use this skill when the task requires observing an API response directly instead of inferring behavior from code.
2. Execute the local script [call_api.py](./call_api.py) with the exact method, URL, and minimal auth configuration.
3. Prefer safe authentication patterns:
	 - `seed-login` for seeded or test-user flows
	 - `bearer-env` when a token already lives in an environment variable
4. Keep secrets out of chat. Prefer `{{env:VARIABLE_NAME}}`, `--auth-env-var`, or seeded credentials loaded from environment variables.
5. Use `--json-body` for structured payloads and `--max-body-chars` to cap noisy responses.
6. If the endpoint is protected, verify the auth flow first and only then call the target endpoint.

## Common invocations

- Health check:
	`python ./call_api.py GET http://localhost:3000/api/health`
- Protected endpoint with seeded login:
	`python ./call_api.py GET http://localhost:3000/api/users/me --auth-mode seed-login --login-url http://localhost:3000/api/auth/login --seed-username seeded-admin@example.com --seed-password <seed-password> --token-json-path accessToken`
- Token-exchange flow using placeholders:
	`python ./call_api.py GET http://localhost:3000/api/users/me --auth-mode seed-login --login-url http://localhost:3000/oauth/token --login-content-type form --login-body '{"grant_type":"password","username":"{{seed_username}}","password":"{{seed_password}}","client_id":"{{env:API_CLIENT_ID}}"}' --seed-username seeded-admin@example.com --seed-password <seed-password> --token-json-path access_token`
- Reuse an existing bearer token from the environment:
	`python ./call_api.py POST http://localhost:3000/api/posts --auth-mode bearer-env --auth-env-var API_BEARER_TOKEN --json-body '{"title":"Seeded smoke test"}'`

## Guardrails

- Sensitive headers like `Authorization` and `Cookie` are redacted by the script.
- Use `--insecure` only for local development with self-signed TLS.
- Do not use this skill as a substitute for browser automation; use a browser-based skill when the flow depends on real page interactions.
