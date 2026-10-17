# Optional accounts and drop-off badges

Both Recycle and City coverage have a Sign in /
My activity button. All existing browsing, guidance and route planning remain
available to guests; signing in never increases paid-provider allowances.

## Use

1. Create a username (3–24 letters/digits/underscores) and a unique password
   (15–128 characters). Usernames are case-insensitive. No email is collected.
2. Plan a route while signed in, then choose **Dropped these off** at a stop.
3. Open **My activity** for an overview, badge collection and material-filtered history.

The overview shows the next milestone, the last 28 UTC days and the five material
categories collected. Six custom vector badges track the first, tenth and
twenty-fifth recycling drop-offs, all five recycling/donation categories (Full
circle), a clothes donation (Second life) and electronics recycling (Tech return).
Each badge displays its requirement, progress or earned date. Lifetime aggregates
include entries older than the latest 50 displayed in History; filtering applies
only to those displayed entries. Material counts mean stops involving that material,
not item counts or quantities. Multiple materials at one stop still count once
toward numeric milestones. General waste never contributes to badge progress.

One completed route stop counts as one action, not one action per item. Recycling
and clothes donations count; general waste alone does not. Mixed general/recycling
stops count once. These are **self-reported milestones**, not verified recycling,
physical arrival, environmental savings, prizes or a leaderboard. A user can create
new routes and self-report again; this is not fraud-proof reward infrastructure.

Failed saving preserves the basket, exposes retry and allows an explicit **Mark
without saving**. Expired sessions require sign-in again. Routes planned as a guest
must be replanned after signing in to receive history-saving tickets. No anonymous
history is collected or retroactively linked to an account.

## Storage and security

The existing ignored SQLite database gains accounts, sessions and dropoffs tables;
existing reports/quotas are preserved. No new dependencies or external auth service.

- Passwords use Python/OpenSSL scrypt (N=2^17, r=8, p=1, random 16-byte salt,
  32-byte digest). Two concurrent password operations maximum. Unknown-user login
  does equal KDF work, and failed logins use a generic error. Credentials are not
  logged or echoed in validation responses.
- Sessions are random 32-byte opaque tokens; only SHA-256 digests are stored.
  Cookies are HttpOnly, SameSite=Strict, Secure on HTTPS, with a fixed seven-day
  expiry. Login rotates the current session; logout invalidates it server-side.
  At most five sessions per account. Expired sessions are purged on database access.
- Account writes require a custom same-origin header and reject foreign Origins.
  No cross-origin permission is granted. JSON bodies are capped at 16 KiB; account
  responses are no-store. Tokens/passwords never enter browser local/session storage.
- Authentication attempts reserve persistent global/network/day/hour allowances
  before password work: 500 global/day, 60 network/day, 20 network/hour. Registration
  additionally allows 100 global/day, 10 network/day, five network/hour. Drop-off
  requests allow 1,000 global/day, 100 network/day, 40 network/hour. Failed requests
  count. Existing vision/routing caps remain unchanged and independent of account.
- Successful authenticated routes issue HMAC-signed per-stop tickets valid for
  24 hours, bound to the account and server-selected materials. They contain no
  origin, destination, route geometry or site identifier. Duplicate ticket
  submissions are atomic/idempotent, including concurrent clicks and lost replies.
- History stores only material types and completion time; no locations, photos or
  free-text item descriptions. The API displays the most recent 50 entries and a
  lifetime recycling count. Accounts/history persist until the user deletes them.
- Password-confirmed account deletion cascades to all sessions/history/badges.
  Community reports are independent anonymous submissions, not account-linked;
  their separate 30-day retention remains. SQLite secure-delete remains enabled.
- Ordinary accounts gain **no reviewer privileges**. Reviewer access continues to
  require its independent secret.

Choices were checked against the [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
and [session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## Deliberate prototype limits

No email verification, password change/recovery, MFA, identity proof, public profile
or account administration. The signup screen warns that password recovery is absent.
Use a prototype-only password; public launch requires a reviewed identity/recovery system,
HTTPS, trusted proxy configuration, abuse protection and persistent storage.
Do not expose the loopback launcher to the internet. Hosting and physical-phone
testing remain user-deferred; private-repository CI is active. This is not a
production security sign-off.

## Contracts and checks

- `POST /api/v1/account/register`, `/login`: username/password, set session cookie.
- `GET /api/v1/account/me`: private profile/history/badges, or `{ "user": null }`.
  Signed-in responses include six `achievements` (requirements, progress, target,
  nullable earned timestamp), `activity` (lifetime material counts and 28 UTC daily
  counts), and `history_count`. The original two-key `badges` mapping is retained
  for compatibility. Aggregates use a consistent SQLite read transaction.
- `POST /api/v1/account/logout`: revoke current session.
- `DELETE /api/v1/account`: password-confirmed deletion of account/history/sessions.
- `POST /api/v1/account/dropoffs`: `{ "ticket": "..." }`; updated profile plus recorded flag.
- Trip stops add nullable `completion_ticket`; guests receive null.

All writes send `X-Najdi-Frli-Action: 1`; the former `X-Goodsort-Action: 1` header
is accepted for compatibility. Backend tests cover hashing, rotation,
expiry, CSRF, quotas, ownership, tampering, concurrency, deletion, privacy and badge
thresholds. Browser tests use temporary databases and simulated paid providers to
exercise signup → route → drop-off → history, both modes, shared navigation, guest
use, failed saves, expired sessions, login/logout and deletion at desktop/narrow widths.
Activity tests cover empty, first, tenth and twenty-fifth milestones at 360/1280px,
keyboard tabs, history filters, and lifetime badges beyond the displayed history.
The fixture server's budget-reset endpoints are test-only, never registered by the app.
