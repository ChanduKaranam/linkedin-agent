# backend/src/backend/integrations/

## Purpose
External service integration clients. Currently contains only the LinkedIn integration. Future integrations (e.g., Ghost CMS for blog publishing) should be added here as separate modules.

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `linkedin.py` | LinkedIn OAuth 2.0 flow + official Posts API publisher. Functions: `oauth_start()` → authorize URL; `oauth_callback(session, code)` → token exchange + member URN fetch + DB persist; `get_connection_status(session)` → `{connected, expires_at, member_urn}`; `publish_post(session, content)` → POST to `/rest/posts`, returns URN from `x-restli-id` header. |

## LinkedIn API Details
- **Auth endpoint:** `https://www.linkedin.com/oauth/v2/authorization`
- **Token endpoint:** `https://www.linkedin.com/oauth/v2/accessToken`
- **Profile endpoint:** `https://api.linkedin.com/v2/userinfo` (OpenID Connect)
- **Posts endpoint:** `https://api.linkedin.com/rest/posts`
- **Required headers:** `LinkedIn-Version: 202503`, `X-Restli-Protocol-Version: 2.0.0`
- **Required scopes:** `openid profile w_member_social`
- **Token TTL:** 60 days — stored in `linkedin_account` table (singleton id=1)

## OAuth Flow
```
User clicks "Connect LinkedIn" in frontend
        │
        ▼
GET /admin/linkedin/authorize (backend)
        │ 302
        ▼
LinkedIn consent screen
        │ redirect with ?code=...
        ▼
GET /admin/linkedin/callback?code=... (backend)
        │
        ├── POST /oauth/v2/accessToken → access_token
        ├── GET  /v2/userinfo          → member_urn (urn:li:person:{id})
        └── upsert_linkedin_account()  → stored in DB
```

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `linkedin.py` — Added `_encrypt_token(plaintext) -> str` and `_decrypt_token(stored) -> str` helpers using `cryptography.fernet.Fernet`. When `LINKEDIN_TOKEN_KEY` is set in `.env`, tokens are stored as `"fernet:<base64>"` in the DB. When not set, tokens remain plaintext (backward compatible). All places that write tokens (`oauth_callback`) now encrypt; all places that read and use tokens (`get_connection_status`, `publish_post`, `delete_linkedin_post`) now decrypt before use. The encrypted ciphertext is never written to logs. Removed logging of `me_data` dict contents and `resp.text[:200]` from `get_connection_status` — these could leak OAuth error responses containing token fragments.

**Reason:** LinkedIn `access_token` and `refresh_token` were stored in plaintext in the `linkedin_account` table. These tokens allow posting to the user's LinkedIn profile — plaintext storage is a high-severity risk if the DB is ever read by an unauthorized party. The Fernet encryption is symmetric and requires the `LINKEDIN_TOKEN_KEY` env var to decrypt, so tokens at rest in the DB are useless without the key.

**Outcome:** Token encryption working. When `LINKEDIN_TOKEN_KEY` is not set, the app behaves identically to before (plaintext). Generate a key with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Existing plaintext tokens in the DB will be re-encrypted on the next OAuth reconnect.

**Watch out for:**
1. If `LINKEDIN_TOKEN_KEY` is set and then lost, stored tokens cannot be decrypted — user must re-connect LinkedIn.
2. The `_decrypt_token` function returns the raw stored string on `InvalidToken` errors, which means a corrupted token would pass through as garbage and cause a 401 from LinkedIn (not a crash). This is intentional fail-soft behavior.
3. LinkedIn requires redirect URI exact match. Remains true.
4. `w_member_social` scope only — no Company Page posting.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `linkedin.py` | Added Fernet token encryption at rest; removed sensitive log fields (`me_data`, `resp.text`) |
| 2026-04-29 | `__init__.py`, `linkedin.py` | Initial creation — LinkedIn OAuth 2.0 client and Posts API publisher |
