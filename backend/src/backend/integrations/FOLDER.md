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
**Session date:** 2026-04-29

**Changes made:**
- Created this folder and all files (`__init__.py`, `linkedin.py`)

**Reason:** Post Studio feature requires one-click LinkedIn publishing. The official API (`w_member_social` scope) was chosen over browser automation to stay within LinkedIn ToS and avoid account bans.

**Outcome:** OAuth flow and publish function implemented. Uses `httpx.AsyncClient` (already in requirements). Token expiry is checked before publish; raises a user-friendly `ValueError` if expired.

**Watch out for:**
1. LinkedIn requires the redirect URI to match *exactly* (including trailing slash) what is registered in the Developer App. Any mismatch returns a 401 at the callback step.
2. The `w_member_social` scope allows posting to the **authenticated user's** timeline only. Posting to Company Pages requires a different scope (`w_organization_social`) and LinkedIn Marketing Developer Platform approval.
3. Access tokens expire after 60 days. There is no refresh token for personal OAuth — the user must re-authorize via the Connect LinkedIn button.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `__init__.py`, `linkedin.py` | Initial creation — LinkedIn OAuth 2.0 client and Posts API publisher |
