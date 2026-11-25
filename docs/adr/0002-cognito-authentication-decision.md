# ADR 0002: Cognito authentication decision and security contract

**Current procedure amendment — 2026-10-21 (subsequent owner approval):** §17 approves own-account invocation with reason/confirmation and recent authentication, separate suspension/notification outcomes, and reviewed restoration. Earlier amendments remain historical; technical choices and C1/D3 stay partially open, and authentication implementation remains paused.

**Current action-design amendment — 2026-10-21 (subsequent owner approval):** §16 records the dedicated Emergency Suspend Admin console action and notification to both founders. Earlier emergency-policy records remain historical; secure mechanics and partial-failure details remain for review, C1/D3 remain partially open, and authentication implementation stays paused.

**Current emergency-policy amendment — 2026-10-21 (subsequent owner approval):** §15 approves immediate protective suspension by either co-founder, other-founder approval for restoration and attributable emergency auditing. It supersedes the earlier pending-policy statements below; operational details and C1/D3 remain partially open, and authentication stays paused.

**Latest governance amendment — 2026-10-21 (subsequent Option A approval):** §14 records other-founder approval for routine administrator grants/privilege changes, with separate individual accounts. Emergency revocation remains an explicit pending procedure; C1 and D3 remain partially open and authentication stays paused.

**Latest scoped amendment — 2026-10-21 (subsequent decision):** §13 records the owner-approved local-development admin MFA exception and separate co-founder accounts. It qualifies earlier MFA wording only within the strict local boundary; C1 and D3 remain pending and authentication remains paused.

Date: 2026-10-14 (Asia/Calcutta).
Status: **Product decision approved; technical configuration proposals await owner review. Documentation only; no authentication implementation or acceptance claimed.**

**Current checkpoint — 2026-10-21 (Asia/Calcutta):** the owner approved the simpler, cost-conscious authentication direction in §12 below. That dated amendment takes precedence over conflicting earlier proposals, including initial linking, customer MFA and the seven-day maximum. Earlier sections preserve their original decision history; C1–C7 details and named D3 authorities remain pending. Authentication remains paused.

## 1. Decision history and precedence

The [Phase 2 baseline](../phase-2-specification-and-plan.md) was approved on 2026-10-13 with phone/email OTP proposed for customers. P2-A implementation was separately authorized on 2026-10-14, but D1 blocked identity work because the provider and security details were unresolved. The owner's subsequent authentication decision on 2026-10-14 explicitly replaces that customer OTP proposal with Amazon Cognito, Google federation and email/password. The original approval and authorization records remain historical facts; they are not retroactively rewritten as approval of Cognito settings.

**Amendment — 2026-10-15 (Asia/Calcutta):** the owner approved initial-release guest read-only browsing (D8) and PostgreSQL-backed wishlist persistence with online cross-device synchronization in P2-A (D9), and clarified that initial customer authentication neither requires nor collects phone numbers. Guests can discover/swipe, search, filter, view eligible published product details and open approved external retailer links without an account. These approvals replace the earlier sign-in-first/optional-guest and unresolved-sync proposals only from this date. They do not approve C1-C7 technical configuration, provider setup or acceptance.

**Final OOTD guest-access amendment — 2026-10-15 (Asia/Calcutta; subsequent decision):** the owner approved all available customer-facing browsing/discovery for guests in P2-A and P2-B, explicitly including the OOTD vertical feed, public outfit images/titles/captions/eligible products, product details, Discover/search/filter/swipes and approved retailer links, with no account or phone number. Earlier dated approvals remain historical. This settles P2-B guest access, not D6 editorial inputs, D7 native access or C1-C7 security configuration; P2-B implementation still needs separate authorization.

This ADR supersedes conflicting current authentication/access requirements in the baseline. Catalog integrity, exact money, admin publication, migration-history and P2-B boundaries remain unchanged; guest/wishlist access follows the dated amendment above. The owner's latest instruction limits this task to documentation and requests review of this diff before authentication implementation begins. Earlier P2-A authorization is retained; it does not resolve the open configuration choices below. Gate B evidence is historical and makes no claim about Cognito.

## 2. Approved product requirements versus technical proposals

**Approved by the owner:**

- Amazon Cognito is the identity provider.
- Customer sign-in supports Google federation and email/password.
- Phone numbers are neither required nor collected in the initial customer-authentication scope; SMS OTP is not a normal customer login method. Email verification/reset codes are not passwordless email-OTP login.
- Customer and admin authentication are separate. Admin access requires strong MFA **and** an explicit current DRIP-side grant.
- Preserve the seven-day session policy, recovery through a verified channel, immediate DRIP-side account disablement/revocation, private-data deletion target within 30 days and minimal approved audit retention.
- PostgreSQL remains authoritative for DRIP account status, grants, sessions and wishlist data. Cognito owns credentials and provider identity. Redis is ephemeral.

- Guest access to all available customer-facing browsing/discovery is approved for P2-A and P2-B/OOTD; sign-in is required for permanent saves and all account-specific functions. Guest requests return only public eligible catalog data, never account information, wishlists, admin operations, unpublished content or other private data.
- P2-A includes PostgreSQL-backed wishlist persistence and online cross-device synchronization. No guest wishlist, silent merge, local authoritative save store or account-specific guest session is authorized.
- Only approved external retailer redirects are enabled initially and are available without DRIP sign-in. DRIP checkout, order placement, payments and settlements remain outside P2-A/P2-B. Future DRIP-owned order placement must require authentication; no order routes/tables or payment behavior are introduced. A retailer may independently require authentication on its own website.

**Proposed, not yet approved:** separate customer/admin Cognito user pools per environment; Cognito managed login with authorization code + PKCE; opaque DRIP sessions after verified Cognito authentication; mandatory TOTP for local admin accounts; explicit user-driven linking only after proving both identities; Mumbai region and SES-based email delivery. No AWS resources, provider accounts, credentials or integrations have been created or tested.

### Guest access and save transition contract

OOTD is public read-only without an account or phone number: show only published, rights-cleared outfits with all required products eligible for public detail display. Recheck eligibility on reads and suppress the entire outfit when content/rights or any required product becomes ineligible. Never return unpublished outfits, private data, wishlist membership or admin controls. Guests may open products, continue into Discover/search/filter/swipes and approved retailer links. Apply the same bounded requests, public visibility and abuse protection as catalog; no login-provider outage may expose private data or remove public safeguards. Discover gesture meanings stay unchanged, and the product-save transition below applies from outfit-linked products. Exact DTO/pagination/editorial execution remains a later P2-B specification task; guest access itself is settled.

Public catalog requests need no Cognito identity or DRIP AccountSession. They use the same eligible/public visibility, exact-money, freshness and destination validation rules for guests and signed-in customers. Public product-ID resolution cannot reveal wishlist membership or private ownership. PostgreSQL remains the catalog truth; ephemeral browsing cursors/rate counters are not guest accounts. Missing/invalid sessions yield 401 on account-specific routes; authenticated customers without admin authorization receive 403. Public browsing is independent of login-provider availability when its own dependencies and abuse controls are healthy; private routes remain fail closed.

On guest right/save, preserve the current product card in transient UI state and prompt sign-in. Authentication does not itself create a save. After authentication, require explicit confirmation for that product and the signed-in account, revalidate public eligibility and authorization, and wait for backend acknowledgement before announcing success or advancing. Cancellation/failure keeps the card with no write; withdrawal/session expiry/save failure shows an honest unavailable/retry state. No durable guest save queue or automatic merge is permitted. Account-scoped caches never become authoritative; other authenticated devices refresh from the server on foreground/open/explicit refresh. See the [baseline transition contract](../phase-2-specification-and-plan.md) for tests and edge cases.

## 3. Pool responsibilities and trust boundaries

| Boundary | Required responsibility | Proposed configuration / review gate |
| --- | --- | --- |
| Customer pool | Cognito-native email/password registration, verification and recovery; Google federation; stable provider subject | Separate from admin pool; email required, phone not required/collected for this scope; no SMS login/recovery fallback. No customer admin grants inferred from claims. Pool sign-in aliases/case rules and password policy need C6 approval. |
| Admin pool | Restricted staff identities, mandatory approved strong MFA, enrollment and recovery | Separate pool and app client; no public self-registration. Proposed local password + required software-token TOTP, no SMS/email MFA fallback, no customer Google federation, and no remembered-device MFA bypass. C1 decides whether this meets the owner's assurance needs or a phishing-resistant workforce solution is required. |
| DRIP identity service | Validate issuer/proof, map identity, enforce account status/session deadlines, disable/delete and link safely | UNIQUE(issuer, sub); explicit customer/admin realm. Equal email addresses across pools never bridge accounts or grants. No Cognito identity pool/AWS credentials for customers is needed. |
| DRIP authorization | Read current AdminGrant and session assurance for each privileged operation | Customer tokens/sessions rejected on admin routes, including a token with a similarly named group. AWS IAM permissions and DRIP catalog grants are distinct. |
| Environment | Prevent test/prod and customer/admin trust crossover | Separate pools/clients, exact issuers, callback/logout allowlists, IAM and secrets. Nothing selected from a request-supplied issuer or environment parameter. |

Google authentication is delegated to Google; Cognito does not apply the pool's local-user MFA to federated users. Consequently, enabling pool MFA alone cannot certify a Google-based admin session. Proposed admin TOTP is not phishing-resistant; no stronger assurance claim is made. [AWS MFA behavior](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa.html).

## 4. Google OAuth and token-validation contract

Propose system-browser Cognito managed login, authorization code flow and PKCE S256. Disable implicit grants and password handling by DRIP. Mobile is a public client without an embedded client secret; an admin web backend may use a confidential client with server-only secrets. Bind each authorization transaction to state, nonce, PKCE challenge, fixed callback and intended realm; use one-time transactions with expiry. A callback URL or successful redirect is not proof of authentication. [AWS authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html).

C2 must name the Google Cloud project owner, OAuth consent configuration/test users, approved scopes, Cognito domain, client IDs and exact per-environment mobile/web redirect and logout URLs. Google's redirect goes to Cognito's `/oauth2/idpresponse`; the Cognito app client then redirects to the registered DRIP callback. Configure Google credentials only in protected provider configuration. Start from AWS's documented `openid email profile` integration, review attribute needs, and discard unused profile data; no Contacts/Drive scopes. Google is customer-only unless separately approved. [AWS social-provider setup](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html).

At the trusted server boundary, require:

- Exact configured Cognito issuer/pool and allowed algorithm RS256; signature from that issuer's JWKS and known `kid`. Reject arbitrary `jku`/key URLs, malformed/unsigned tokens, algorithm confusion and oversized input.
- Expiry and issued-at/time bounds with a small explicitly configured skew; correct `token_use`; ID-token `aud` or access-token `client_id` matching the intended client. Check required access scopes and any configured resource audience.
- ID tokens serve identity exchange only; they are not accepted as API access tokens. Raw Google tokens are not accepted as Cognito or DRIP sessions. Verify nonce and any required OIDC token bindings in the selected callback/exchange flow.
- Bounded JWKS caching and controlled refresh on unknown key; untrusted/unknown keys fail closed. Do not blindly trust cached account status because keys are cached.
- Realm/client separation, verified-email state and account mapping before session creation. No client-supplied `account_id`, `admin` flag or email string selects the principal.

These checks follow [AWS JWT verification guidance](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html). Exact Python library and callback topology are implementation choices to validate after C2/C4; no new dependency is approved merely by naming this protocol.

## 5. Session expiry, revocation and immediate disablement

**Approved:** customer session policy remains seven days. **Proposed interpretation (C4):** an absolute 168-hour DRIP deadline from the qualifying authentication event, not a sliding window; refresh/activity must not move it. Shorter admin limits from the earlier proposal (eight hours, recent MFA within 15 minutes for privileged writes) remain proposed, not automatically approved.

Recommended default retains opaque DRIP AccountSession handles, stored as hashes server-side. Cognito code/token verification establishes a session once; account-specific and privileged API operations authenticate the DRIP session and query PostgreSQL status, expiry/revocation and current grant; public eligible catalog reads require no session and expose no private data. No independent raw-Cognito-JWT route may bypass these checks for protected operations. Native secrets go in secure storage; admin browser sessions use HttpOnly Secure SameSite cookies with CSRF/origin protection. Account caches are cleared on logout/switch/deletion.

C4 must settle Cognito token custody, refresh strategy, local versus provider logout, absolute/idle expiry, reauthentication and per-device session correlation. If Cognito refresh tokens are retained, propose 15-minute access/ID tokens, refresh lifetime no longer than seven days, rotation with a small reviewed retry grace and no deadline extension. Encrypt necessary provider refresh secrets under managed keys; do not put raw refresh tokens in logs or claim a hash can be sent back to Cognito. The alternative of no retained Cognito refresh tokens needs an explicit provider-logout strategy. These alternatives are not both approved. Rotation does not extend the original refresh expiry and is incompatible with `REFRESH_TOKEN_AUTH`. [AWS refresh documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-refresh-token.html).

A valid JWT signature/expiry does **not** establish that Cognito has not revoked it. Short token lifetimes alone do not meet immediate DRIP revocation. [AWS revocation limitations](https://docs.aws.amazon.com/cognito/latest/developerguide/token-revocation.html).

- For DRIP disable/delete/logout-all/grant-revoke, commit the authoritative PostgreSQL block first. Every subsequent protected authorization check rejects; sensitive transactions recheck status/grant before commit. Document in-flight request handling rather than claiming already completed actions can be undone.
- Revoke the appropriate Cognito token family/global session or disable the provider account as applicable; record and retry failures without reopening DRIP access. Current-device logout must not silently mean all-device logout. Clearing a cookie alone is insufficient.
- Require all normal disable/reset/grant operations through the controlled service. Out-of-band Cognito console disablement, password reset or provider compromise needs an approved synchronous status check or enforceable propagation design. Asynchronous events/reconciliation alone cannot honestly promise zero-delay detection. This is a C4 blocker; no immediate-revocation claim until demonstrated.
- Clear the Cognito managed-login session when applicable. Cognito logout does not sign the user out of Google. Seven-day reauthentication must not be silently renewed from an old browser/provider session; approve and test the precise `prompt`/`max_age` behavior and fresh-auth evidence. [AWS logout semantics](https://docs.aws.amazon.com/cognito/latest/developerguide/logout-endpoint.html).
- AccountSession stores realm, issuer/subject binding, authentication time, expiry, revocation and proven assurance. Do not assume a generic `amr`/group claim proves a recently completed MFA challenge. C1/C4 must demonstrate the evidence available in the chosen admin flow. No schema change is made now.

## 6. Email verification, passwords and recovery

Cognito-native signup must verify the email before DRIP activates the account. Google identities require trusted mapped `email_verified=true` and issuer/subject validation; missing or false verification must not be silently promoted. Self-service app-client permissions must not permit setting verification flags. Email change requires verification of the replacement before it becomes a recovery destination, with notifications and session handling defined in C6.

Passwords are entered into the approved Cognito experience, not stored/hashed by DRIP, captured in request logs, or copied into catalog records. Proposed customer password policy is at least 12 characters with Cognito-supported controls and password-manager/paste support; exact requirements, threat protections and tier/cost are C6 decisions.

Set an explicit recovery policy using verified email only; do not leave defaults that might select a phone number. Cognito verification/reset codes remain verification/recovery, not the old routine OTP login API. Google-only users recover their Google identity through Google; do not set a local password on a federated profile as an automatic recovery workaround. For an explicitly linked native identity, use its approved verified-email recovery path. [AWS password/recovery settings](https://docs.aws.amazon.com/cognito/latest/developerguide/managing-users-passwords.html), [AWS linking cautions](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-identity-federation-consolidate-users.html).

Admin recovery is distinct: proposed password reset via verified staff email with TOTP still required; loss of TOTP must not become an email-only MFA bypass. Proposed lost-factor process suspends access, requires documented identity proof and two authorized operator approvals, revokes sessions, and requires new factor enrollment before reactivating the grant. C1 must approve who can perform it, assurance/evidence, notifications, audit and emergency access. No shared admin accounts, support-issued permanent passwords or invented Cognito recovery-code capability. Email/SMS MFA interacts with password-recovery destinations; required MFA can make recovery impossible if the same channel is used for both. Validate the exact approved setup in a non-production pool, including total factor loss. [AWS MFA/recovery interaction](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa.html).

## 7. Identity linking and account collisions

Key identities by configured pool issuer + immutable Cognito `sub`; email is neither a primary key nor authorization proof. An email/password account and a Google identity with the same verified email must **not** be automatically merged, elevated or allowed to claim each other's wishlist. No pre-signup auto-link-by-email trigger. Do not use forced alias migration to take over an existing account.

C3 must choose an explicit linking design or disable self-service linking for the pilot. Recommended safe starting position: no automatic linking; block ambiguous duplicate account creation from gaining authenticated DRIP access and show a generic instruction to use the original method or verified support. The server may need a protected normalized-email collision index; approve its retention/encryption/keying and case rules before adding a field. Do not strip dots/plus suffixes or invent equivalence rules.

If approved, linking requires recent authentication of the existing DRIP account **and** fresh proof of the Google identity, user confirmation, CSRF/replay protection, uniqueness checks and an audit event. Link the Google provider's stable subject under an IAM-restricted backend operation. Never trust a requested email or provider ID from the browser. Two existing DRIP/Cognito profiles require a reviewed reconciliation plan; do not delete a federated profile or overwrite saves just to make linking succeed. Preserve the canonical DRIP account ID and explicitly resolve collisions; revoke affected sessions after a completed change.

Cognito linking is privileged and requires trusted identity attributes; Google source linking uses `Cognito_Subject`. A provider profile already created by first federated sign-in has additional constraints; validate the complete scenario before offering it in UI. [AWS linking API](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminLinkProviderForUser.html). No linking endpoint or data migration is created by this decision.

## 8. Deletion, rate limits and privacy

**Approved deletion target:** private data removed within 30 days of an authenticated, confirmed deletion request. Disable DRIP access and revoke sessions immediately; processing time is not a 30-day login grace period. Delete DRIP private associations/caches and the relevant Cognito profile; unlink provider associations as required. Deleting a Cognito user does not delete the person's Google account. Federated re-login must not silently recreate a deletion-pending account. [AWS user deletion API](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminDeleteUser.html).

C7 must define the minimum audit fields, retention periods, legal exceptions, backup expiry/restore controls and deletion-pending suppression record. Retain only approved pseudonymous actor/action/time/result evidence where necessary; do not carry raw contact details or tokens into audit receipts. Catalog/source approval retention is a different policy and cannot justify keeping all customer identity data. Track pending provider deletion, retry idempotently, alert before the deadline and report failures honestly; reconciliation must not restore access. Specify how backup restores replay deletions and prevent resurrection.

Apply abuse protection to unauthenticated public catalog browsing as well as signup, login, confirmation resend, password reset, OAuth exchanges and linking. Propose per-IP plus keyed-identifier controls, resend cooldowns, progressive throttling, retry limits, generic safe errors and security alerts. Exact quotas, spend ceilings and recovery-code lifetimes need C6/provider compatibility review; the old universal five-minute/five-attempt OTP assumption is superseded. DRIP Redis limiter failure must fail closed on rate-limited public browsing/identity endpoints rather than enabling unlimited anonymous reads or sensitive actions. Catalog limits in the baseline remain proposed technical thresholds; C6 does not reopen the approved right to browse without an account.

Direct Cognito endpoints/managed login are not protected merely because FastAPI is rate-limited. Review Cognito protections, quotas and WAF for that boundary; test legitimate users behind shared IPs and admin TOTP enrollment. Enable applicable user-existence error protection, but test signup/alias/recovery/federation separately rather than claiming every provider response is non-enumerating. [AWS error behavior](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pool-managing-errors.html), [AWS WAF integration](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-waf.html).

No collected phone attribute in initial customer authentication, contacts, Google API access unrelated to login, advertising identifiers, raw passwords/codes/tokens, full callback URLs or full email identifiers in logs. Persist the minimum provider subject/verification metadata needed; document Google/AWS email/data transfers. Secrets belong in approved secret storage, never mobile bundles or Git. Redact proxy, application, provider-trigger and error logs. No credentials or personal sample accounts belong in this document.

## 9. Configuration approvals still required

| ID | Owner decision required | Proposed technical default / reason |
| --- | --- | --- |
| C1 | Exact admin factor, enrollment, recent-MFA proof, lost-factor recovery, approvers and emergency process | Separate restricted local-admin pool, required TOTP, no remembered-device bypass or SMS/email-MFA fallback; verified-email password reset still requires TOTP. Approve or require a phishing-resistant workforce alternative. Eight-hour admin maximum/15-minute privileged freshness remain proposals. |
| C2 | Google project/consent owner, scopes/attribute mapping, test versus production publishing, Cognito domains, mobile/web callback/logout allowlists and app-client ownership | Customer-only Google federation; code + PKCE; public mobile client/no secret; backend-held admin secrets. Test both redirect legs and reject arbitrary return URLs. |
| C3 | Linking enabled now or staged, collision handling, proof/confirmation, email normalization/index and reconciliation of existing profiles | No automatic linking; block ambiguous access. Explicit prove-both-identities flow only after approval; no destructive account merge. |
| C4 | Exact seven-day enforcement, session/token custody, refresh/rotation, idle limits, logout scope, provider-side disable propagation and fresh-auth semantics | Absolute 168-hour DRIP session, PostgreSQL checks on every protected request; shorter admin policy. Decide opaque-session versus JWT+durable-session binding and prove immediate revocation; neither signature-only checks nor stale caches suffice. |
| C5 | AWS account/environment ownership, Cognito region, data residency expectations, SES region/domain/sender/reply-to, DNS, sandbox exit, delivery/bounce/complaint operations and budget | Evaluate ap-south-1 (Mumbai) for both pools and compatible SES sending; do not assert exclusive India residency for Google/AWS processing or logs. Production requires approved sender and deliverability evidence. |
| C6 | Password policy, verified-email change/recovery behavior, customer MFA posture, Cognito plan/protections, rate quotas and email budget | Verified-email recovery only; no phone/SMS dependency. Managed login to keep passwords out of DRIP; exact thresholds must match supported Cognito behavior. |
| C7 | Minimum identity/security audit fields and retention, deletion workflow/backup handling, 30-day measurement and incident escalation | Minimize/pseudonymize audit; durable deletion status and retries. Do not reuse catalog's proposed 90-day source-artifact policy for customer data. |

Region/email setup must be checked against the selected region's Cognito/SES compatibility and account ownership. Cognito's default email configuration has restrictions; do not infer production readiness from test mail. [AWS email configuration](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-email.html). C1-C7 are not silently approved by the product decision. They block only their dependent design/implementation; no provider selection question is repeated.

## 10. Required verification and acceptance evidence

| Area | Required future tests/evidence |
| --- | --- |
| Configuration/flows | Real Google and native email/password signup/login on supported mobile and admin web; verified-email gating; no phone collection in forms, scopes, mapped attributes or stored customer-auth records, and no normal SMS login; wrong environment/client/pool rejected. Real SES/Google setup tested separately from mocks. |
| Tokens | Wrong signature/issuer/client/audience/token_use/scope, algorithm confusion, unknown/rotated key, expired/future times, nonce/state/PKCE mismatch, code replay and untrusted key URLs; ID/Google token misuse rejected. JWKS failure follows approved cache policy. |
| Admin isolation | Customer session rejected despite same email/group; no self-grant; required MFA enrollment, recent-assurance checks, revoked grant, missing factor, recovery and emergency flow. Prove actual MFA evidence rather than invent claims. |
| Guest access and transition | Unauthenticated discovery/swipes/search/filters/details/approved external links return only eligible public data; guest access to account/wishlist/admin/unpublished data is denied. Test anonymous abuse limits and limiter failures, provider outage without private fallback, preserved card on cancellation, post-auth confirmation, no automatic save/guest account/session/merge, withdrawn product, account switch, backend failure and acknowledgement before success. |
| OOTD guest boundary (P2-B, future) | No account/phone needed for feed/images/titles/captions/eligible products, product details, Discover navigation or approved retailer links. Test guest/signed-in public-field parity, draft/private/wishlist-membership/admin denial, full-outfit suppression on rights/content/product withdrawal, cursor-page rechecks, anonymous abuse limits/outages and the unchanged confirmed product-save flow on both native platforms. No test is claimed run; D6/D7 and separate P2-B authorization remain required. |
| Wishlist synchronization | P2-A server persistence and same-account second-device refresh after save/remove/clear; two-account isolation, account-switch cache clearing, no local authoritative writes or guest wishlist. |
| Sessions | Exact seven-day boundary, refresh not extending deadline, second-device behavior, logout versus logout-all, retained browser/Google SSO, immediate DRIP disable/revocation, Cognito-console/out-of-band changes and dependency outages. Test already-issued JWTs after revocation. |
| Recovery/linking | Unverified or changed email, reset throttling/enumeration, Google-only recovery, matching-email collision, proof of only one identity, both-profile-existing case, concurrent link, cancelled confirmation and no save/grant takeover. |
| Deletion/privacy | Immediate access denial, authenticated request, retries during Cognito failure, within-30-day completion measurement, deletion-pending re-login suppression, minimal audit, backup restoration controls and log redaction. |
| Regression | Existing configuration/error/UUID/migration tests; identity/catalog isolation; lint/type checks; shared contracts, web/mobile builds, Expo checks and fresh-source verification. New DB changes require additive Alembic revisions and disposable migration tests. |

Use the [baseline verification commands](../phase-2-specification-and-plan.md) and [isolated setup](../setup.md); add focused identity and UI/contract tests only in a later authorized implementation task. No provider calls, AWS changes, email sends, dependencies, migrations, runtime tests or native builds were performed for this ADR. Documentation checks cannot establish Cognito configuration correctness or P2-A acceptance.

## 11. Review gate

- [x] Owner authentication product change recorded 2026-10-14: Cognito, Google + email/password, no required phone/routine SMS OTP, separate admin authentication with strong MFA + grants.
- [x] Owner amendment recorded 2026-10-15: no phone collection; D8 initial guest public browsing/approved links and D9 P2-A server-backed cross-device wishlist; authenticated, explicitly confirmed, backend-acknowledged saves. Checkout/order/payment scope remains excluded.
- [x] Final OOTD guest-access amendment recorded 2026-10-15: P2-A/P2-B public browsing is guest-accessible; published rights-cleared eligible outfits only, private functions protected. D6/D7 and C1-C7 remain unresolved; no P2-B implementation approval.
- [x] Seven-day policy, verified-channel recovery, immediate disable/revocation, private deletion within 30 days and minimal approved audit retention retained.
- [ ] Owner reviews this proposed technical diff and resolves C1-C7 for affected implementation.
- [ ] Provider-specific contracts and tests demonstrate the approved session/MFA/recovery behavior.
- [ ] Authentication implementation resumes only after this documentation review and required decisions; no new broad P2-A authorization is requested.
- [ ] P2-A acceptance remains outstanding; P2-B remains unauthorized.

## 12. Owner-approved authentication direction — 2026-10-21

The owner explicitly approved the following direction on 2026-10-21 (Asia/Calcutta). This is direction-level approval, not blanket closure of C1–C7, approval of a configured provider flow, or acceptance of authentication implementation. It supersedes conflicting earlier proposals only from this date; the October 13–15 approvals and historical verification evidence are not rewritten.

### Approved direction

1. Retain Amazon Cognito and customer Google federation plus email/password. Do not collect customer phone numbers or use SMS OTP for the initial release.
2. Customer MFA is **not compulsory at initial launch**. Whether to offer optional customer MFA, and its configuration, remain separately reviewable under C6.
3. Keep customer and admin authentication separate. Administrators require stronger authentication including MFA and explicit current DRIP-side grants; C1 still determines the factor, enrollment, recovery, approvers, emergency procedure and freshness policy. No TOTP or other particular factor is approved by this amendment.
4. Prefer the simplest compatible Cognito-managed login flow for the initial release, subject to C2 compatibility review. This approves the preference, not a specific pool/client topology, OAuth implementation or Google project/domain/callback/credential configuration.
5. Do not automatically link identities based on matching email. **Keep account linking disabled initially** unless a separately reviewed, explicitly authorized linking flow is approved. Collision, normalization and recovery rules remain C3 work; disabling linking does not justify silent merging, granting access to another account, or destructive reconciliation.
6. Customer sessions have a **hard maximum lifetime of seven days**, with a separately defined idle timeout. Refresh or activity must not extend an existing session past that maximum. C4 must define enforceable start/fresh-auth evidence, idle timeout, access-token lifetime, refresh-token settings, storage/custody, logout and provider-side revocation semantics. Earlier wording treating the hard maximum itself as merely optional is superseded; exact enforcement remains pending.
7. Use short-lived access credentials and a protected refresh flow. Evaluate refresh-token rotation against the selected Cognito flow and approved session boundary; rotation is not yet selected or configured. No exact token duration, refresh grace period, opaque-handle versus JWT topology or token-storage design is approved here.
8. DRIP must enforce authorization and account status server-side. Token validity alone cannot grant access to another account's data or override a DRIP-side revocation. PostgreSQL remains authoritative for DRIP account status, sessions, admin grants and wishlist ownership; Redis remains ephemeral.
9. Prefer owner-controlled AWS environments, a verified DRIP email sender and explicit spending/delivery monitoring. Actual owner, region/residency, sender/domain, budget, SES setup and production delivery configuration remain C5 decisions. No cost or delivery capability is claimed verified.
10. Use provider-managed password and recovery capabilities where compatible, verified-channel recovery and layered abuse protection. Exact password/recovery rules, optional customer MFA, quotas, protection tiers and email/spending limits remain C6 decisions.
11. Preserve immediate DRIP-side denial/revocation and the private-data deletion target within 30 days. Audit fields/retention, backup expiry, deletion retries, restoration suppression and escalation remain C7 decisions; no retention period or lifecycle verification is inferred.

Guest public browsing, the explicit guest-save confirmation/backend-acknowledgement transition, authenticated PostgreSQL-backed cross-device wishlist, exact-money and catalog constraints remain unchanged. P2-B/OOTD implementation remains separately gated; no checkout, order or payment capability is authorized.

### Remaining decision register and implementation gate

This table is the current interpretation of §9 after the direction approval. **Every row remains PENDING**; a settled direction is not a resolved detailed contract.

| Item / status | Direction now settled | Required details or appointments still missing |
| --- | --- | --- |
| C1 — PENDING | Separate admin authentication, stronger authentication including MFA and current DRIP grants | Exact factor, enrollment, assurance evidence, recovery, approvers, emergency procedure and freshness/session policy |
| C2 — PENDING | Prefer the simplest compatible Cognito-managed login | Compatibility review, Google project ownership, scopes/mapping, environment/client setup and exact callback/logout allowlists; no identifiers invented |
| C3 — PENDING | Linking disabled initially; no automatic same-email linking | Collision, normalization/protected-index and recovery rules; any future linking requires separate review and explicit authorization |
| C4 — PENDING | Hard seven-day maximum plus separately defined idle timeout; short-lived access credentials and protected refresh; server-side authority | Enforceable session/start/fresh-auth/idle-expiry contract, exact token lifetimes, refresh/rotation settings, storage/custody, logout and provider-side revocation; no rotation approval inferred |
| C5 — PENDING | Prefer owner-controlled AWS, verified DRIP sender and spending/delivery monitoring | Actual AWS/environment ownership, region/residency, sender/domain, SES/production delivery setup, operations and budget |
| C6 — PENDING | Customer MFA not compulsory; provider-managed password/recovery where compatible, verified-channel recovery and layered abuse protection | Optional customer MFA decision/configuration, exact password/recovery policy, protection tier, quotas and email/spending limits |
| C7 — PENDING | Immediate DRIP-side denial and private deletion within 30 days | Minimum audit fields/retention, backup expiry, deletion retries, restoration suppression, escalation and verified lifecycle evidence |
| D3 — PENDING | Admin authority must be explicit; no implicit grants | Named **primary and backup admin/grant authorities**, plus designated catalog rights/source approvers; existing source/rights/host/branding inputs also remain open |

The required documentation-review gate and named D3 authority remain unresolved. Authentication is **not implementation-ready** and stays paused until the required C1–C7 details, documentation review and D3 appointments are resolved. Earlier P2-A authorization remains historical; this amendment does not release that pause. Future tests must cover non-compulsory customer MFA, disabled initial linking/collision isolation, the hard maximum and approved idle/refresh behavior, current server-side status/grants, recovery and deletion. No tests were run or new test code created by this amendment.

The [P2-0 contract checkpoint](../p2-0-contracts-and-acceptance.md) and [Phase 2 checkpoint](../phase-2-specification-and-plan.md) record the same approval boundary. The October 20 [readiness audit](../p2-a-readiness-audit.md) is retained as a dated assessment, not edited into evidence that these directions were approved earlier. No application, provider, dependency, configuration, schema or service change is made.

## 13. Local-development admin exception and co-founder accounts — 2026-10-21

This subsequent owner-approved amendment on 2026-10-21 (Asia/Calcutta) narrows the earlier same-day admin MFA direction **only for strictly local development**. It does not erase §12 or earlier decisions, close C1/D3, or authorize implementation.

- Admin MFA is not required initially only on an instance restricted to the development machine, using development data, with **no public tunnel or shared remote exposure**. A development label alone does not qualify an instance; LAN/shared-remote access falls outside this exception.
- Remotely accessible shared/test environments and production retain the existing admin MFA requirement unless the owner separately reviews and explicitly changes that policy. Moving outside the local boundary cannot carry the exception forward.
- Both co-founders are intended admin users, each with a **separate individual account and admin profile**. Shared administrator credentials are not allowed. No names, emails, provider identities or credentials are designated by this amendment; “admin profile” does not prescribe a new database table.
- Both founders may have equivalent local admin permissions. Ordinary admin access does **not** automatically authorize granting or revoking other administrators; that authority must be explicitly designated.
- Initial local admin grants require an explicit, controlled **development-only setup procedure**, not a public endpoint, signup-derived privilege or user-editable role flag. Its implementation and operator authorization remain to be specified; no bootstrap command, bypass flag, account or grant is created here.
- Every administrative operation must remain attributable to the individual founder account. The MFA exception does not waive authentication, current DRIP grants, server-side authorization/account status, revocation or individual audit attribution.

| Decision / status | Approved direction | Still pending |
| --- | --- | --- |
| C1 — PENDING | Initial MFA exception for the strictly local boundary only; MFA retained for remotely accessible shared/test and production | Eventual shared-environment admin MFA method, enrollment, recovery, assurance evidence, approvers, emergency procedure and freshness/session policy |
| D3 — PENDING | Both co-founders are intended individual admin users; equivalent local admin permissions permitted, no shared credentials or automatic grant-management power | Formally designated actual founder accounts/identities, primary/backup grant and revocation authority, controlled local setup authorization/procedure and designated catalog rights/source approvers |

Future contract/tests must distinguish qualifying local development from public-tunnel, LAN/shared-remote and production cases; prove separate principals and attribution, explicit grants, and denial of unauthorized grant/revoke attempts or role-flag escalation. These are acceptance requirements for later authorized work, not tests executed now.

C2–C7 details, remaining D3 inputs and the documentation-review gate remain open as applicable; authentication implementation remains paused. All other approved customer/session/privacy, guest/wishlist and architecture requirements remain unchanged. No provider users, credentials, services, databases, application/configuration/test code or migrations were created or changed. P2-B/OOTD remains separately gated.

## 14. Option A: mutual approval for administrator-access changes — 2026-10-21

The owner approved Option A on 2026-10-21 (Asia/Calcutta), subsequent to the local-development exception in §13. This amendment records governance direction without appointing actual identities, closing C1/D3 or claiming implementation. Earlier decisions and verification remain historical.

1. Both co-founders will have separate individual administrator accounts with equivalent ordinary admin permissions. Shared administrator credentials remain prohibited.
2. Either founder may request an administrator grant or privilege change, but **the other founder must approve it**. A founder cannot approve their own request or grant themselves additional privileges. Ordinary admin permission is not unilateral authority to change administrator access.
3. Each request, approval, grant and revocation must be attributable to the individual accounts involved. Actual identities, who executes an approved change and detailed request/approval/audit mechanics still require designation and review; no names, emails, credentials or account identifiers are invented.
4. The initial two founder grants require a documented, controlled bootstrap process **restricted to local development**. No public bootstrap endpoint or unrestricted role-editing mechanism is permitted. This is a distinct initial setup process, not an excuse to bypass mutual approval for later routine changes; its exact operator authority and procedure remain to be reviewed.
5. Shared, remotely accessible test and production environments retain existing admin MFA requirements. The local-development MFA exception remains limited to an instance restricted to the development machine, development data, and no public tunnel or shared remote exposure. This amendment does not expand that exception.

### Emergency revocation — explicit pending owner decision

**PENDING under C1/D3:** approve a separate emergency-revocation procedure for a suspected compromised administrator account. Specify who may invoke it, the action and scope they may take, how the invocation and revocation are audited against individual accounts, and how access is subsequently reviewed or restored. No founder or other actor is implicitly appointed emergency authority here.

Immediate protection against a suspected compromised account **must not be delayed by the ordinary approval workflow**. Routine mutual approval and emergency revocation are not the same process; do not require approval by the suspected compromised account to protect access. This urgency requirement does not silently authorize a particular unilateral mechanism, recovery shortcut or restoration policy. Those details require explicit owner approval before dependent implementation.

| Decision / status | Direction now approved | Details still open |
| --- | --- | --- |
| C1 — PARTIALLY OPEN | Option A routine mutual approval; existing environment-specific MFA policy retained | Shared-environment MFA factor, enrollment, recovery, assurance, session/freshness and emergency policy, including emergency-revocation invocation, audit, review/restoration and required documentation review |
| D3 — PARTIALLY OPEN | Two separate founders with equivalent ordinary admin permissions; other-founder approval for requests | Actual founder identities/accounts and formal request/approval/grant/revocation authority designations, primary/backup responsibilities, controlled local bootstrap procedure, emergency authority and catalog rights/source approvers |

Authentication remains paused until its applicable remaining decisions and documentation-review gate are resolved. Other pending C/D items are unchanged. No accounts, approvals, grants, revocations or provider configuration have been created; no code, tests, services or database operations were performed. P2-B/OOTD remains separately gated.

## 15. Owner-approved emergency administrator revocation — 2026-10-21

The owner explicitly approved this policy on 2026-10-21 (Asia/Calcutta), after §14's Option A amendment. This supersedes earlier pending statements only for emergency protective authority, restoration approval and the audit requirements below. Earlier records remain historical; approval of this policy is not approval of the remaining operational design or implementation.

### Approved emergency policy

1. Either co-founder may immediately suspend the other co-founder's administrative privileges when account compromise is suspected. Routine mutual approval must never delay protective suspension or revocation.
2. This authority is protective only: it does not allow self-granting new privileges, self-approval of access changes, or bypassing mutual approval for ordinary administrator grants. Separate individual accounts, equivalent ordinary admin permissions and attributable actions remain required.
3. The protective action must invalidate or revoke affected DRIP administrative sessions as supported by the approved session design. Privileged API requests must be denied promptly using authoritative DRIP-side grant/session state in PostgreSQL; expiry of an already-issued token alone is inadequate. Exact session/token enforcement mechanics remain pending C4; Redis is not authoritative.
4. Preserve a security audit record with the acting founder, affected account, timestamp, reason/category, action taken, resulting state and subsequent review/restoration outcome. Never log passwords, tokens, recovery codes or other authentication secrets. These required emergency audit fields are now approved; exact retention and backup handling remain pending C7.
5. The suspended founder cannot approve their own restoration. Restoration requires approval from the other founder after reviewing the incident.
6. Restoration must re-establish required authentication assurance and valid admin grants. Access must not return automatically because time has passed or the identity provider becomes reachable again.
7. Limit the action to the affected administrator's DRIP privileges and necessary DRIP sessions. Do not automatically delete their account, personal data or customer access; any broader action requires a separately authorized incident procedure.
8. MFA remains waived only for strictly local development: the development machine, development data, no public tunnel or shared remote exposure. Shared/remote test and production retain admin MFA requirements. Controlled local bootstrap remains unchanged; this policy creates no public bootstrap endpoint or unrestricted role editor.

### Remaining details and implementation gate

**C1 and D3 remain PARTIALLY OPEN.** The approved actors are either co-founder for protective suspension and the other founder for restoration approval; their actual identities/account mappings and formal primary/backup responsibilities are still undesignated. No names, email addresses, credentials or account identifiers are invented.

The following remain pending separate review:

- **C1/D3:** operational method and secure interface for invoking emergency suspension; how the other founder is independently notified and the incident reviewed; detailed restoration and identity-recovery procedure. Existing shared-environment MFA factor, enrollment, recovery, assurance and session/freshness details also remain open.
- **D3:** actual founder identities/account mappings, formal primary/backup responsibilities, controlled local bootstrap procedure and other outstanding authority/source-approver designations.
- **C4:** technical session/token invalidation, revocation and enforcement details, including the boundary for affected administrative sessions; no token duration, interface or provider mechanism is selected here.
- **C7:** exact audit retention and backup handling; no retention period or verified lifecycle is inferred.
- **Documentation review:** the required review gate remains unresolved. This policy approval does not release authentication implementation; P2-1 remains paused. Other unresolved decisions remain open, and P2-B/OOTD stays separately gated.

This is a documentation amendment only. No code, endpoints, permissions, schemas, migrations, tests or configuration were implemented; no users were provisioned and no providers, services or databases were accessed or changed.

## 16. Emergency Suspend Admin action approval — 2026-10-21

The owner explicitly approved this design direction on 2026-10-21 (Asia/Calcutta), after §15. This amendment supplements that emergency policy; earlier amendments remain historical. The corresponding records are [P2-0 §14](../p2-0-contracts-and-acceptance.md) and [Phase 2 §17](../phase-2-specification-and-plan.md). Approved requirements below are distinct from proposed failure presentation and pending technical mechanisms.

### Approved capability and behavior

1. Provide a dedicated **Emergency Suspend Admin** action in the admin console. Either co-founder may use it to suspend the other co-founder's administrative privileges when compromise is suspected, without waiting for routine mutual approval.
2. Enforce immediate DRIP-side denial by changing authoritative grant/session state in PostgreSQL and rejecting subsequent protected API requests. Token expiration alone is insufficient; Redis is not authoritative. This action is protective only and cannot confer new privileges, permit self-approval or bypass ordinary grant approval.
3. Record an attributable audit event containing the initiating founder, affected account, timestamp, reason/category, action, result and subsequent review/restoration outcome. Notify **both founders** that the emergency action occurred. Audit records and notification content must never expose passwords, tokens, recovery codes or other authentication secrets.
4. Restoration requires approval from the other founder after incident review; the affected founder cannot approve their own restoration. Required authentication assurance and valid admin grants must be re-established. No automatic restoration on elapsed time or identity-provider recovery.
5. Limit suspension to administrative access and the necessary DRIP sessions/grants. Do not automatically delete the affected person's account, personal data or customer access.
6. Admin MFA remains waived only for strictly local development on the development machine with development data and no public tunnel or shared remote exposure. Remotely accessible shared/test and production retain the existing admin MFA requirements.
7. Fail safely: never report successful suspension unless DRIP has confirmed the authoritative access-state change that denies privileged access. A button click, request dispatch, token expiry or notification delivery is not such confirmation. A partial failure must not silently restore privileges or be presented as a completed emergency operation.

### Proposed user-visible partial-failure contract — for the next design review

The following presentation distinguishes confirmed facts from uncertainty without selecting a transaction, endpoint, retry, notification or provider mechanism. Exact wording and operational handling remain proposed.

| Confirmed outcome | Proposed user-visible behavior |
| --- | --- |
| Authoritative suspension and required access denial confirmed; no outstanding operation failure | Show suspension confirmed. Report notification delivery only to the extent actually confirmed, separately from the suspension result. |
| Authoritative change failed, or a timeout leaves its outcome unknown | Show “Suspension not confirmed” with failure/unknown status; do not assert that the target is suspended or still active. Surface the need to verify authoritative state through the reviewed secure procedure. Retry/reconciliation mechanics remain pending. |
| Authoritative suspension confirmed, but notification is failed, pending or unknown | Show “Admin access suspended; notification failed/pending/unconfirmed” as appropriate. Do not claim both founders received it or undo the suspension. Delivery-failure escalation and verification remain pending. |
| Grant/session enforcement or required audit completion is incomplete/uncertain | Show “Emergency operation incomplete” and only confirmed state facts, without an overall success claim. Do not claim all privileged access is denied if enforcement is unconfirmed. Keep any confirmed protective restriction; exact audit-failure handling, reconciliation and escalation require review. |

Notification failure must not be mistaken for failed suspension; a delivered notification must not be mistaken for successful suspension. No retry may silently restore privileges. No recovery channel, service or automatic retry policy is selected here.

### Remaining decisions and gates

**C1 and D3 remain PARTIALLY OPEN.** This approval settles the dedicated admin-console capability and notification to both founders, superseding earlier statements that the entire invocation/notification direction was unspecified. It does not approve the following details:

- **C1/D3:** secure exposure and misuse protection for the action; whether fresh authentication or other immediate assurance is required in each environment. The existing MFA environment boundary is unchanged, not a new fresh-auth policy.
- **C1/D3:** notification delivery, delivery-failure handling and independent verification by both founders; incident review, evidence handling, detailed restoration and identity recovery.
- **C4:** durable grant/session revocation mechanics, in-flight requests and provider-side changes; exact confirmation, partial-failure, audit coordination and reconciliation behavior. No provider-side operation substitutes for authoritative DRIP denial.
- **C7:** audit retention, deletion and backup handling.
- **D3:** actual founder identities/account mappings and formal authority/primary-backup designations; other outstanding local-bootstrap and catalog-source authority details remain open. No names, account identifiers or credentials are invented.
- **Documentation review:** the required review gate remains unresolved. Authentication implementation remains paused until the required decisions, authority designations and documentation review are satisfied; this is not P2-1 implementation authorization. P2-B/OOTD remains separately gated.

No UI components, endpoints, permissions, schemas, migrations, tests, configuration or dependencies are created by this amendment. No users/providers/notification services are provisioned or configured, no service operations or database access occur, and no new software verification is claimed.

## 17. Emergency admin-suspension procedure approval — 2026-10-21

The owner approved this procedure on 2026-10-21 (Asia/Calcutta), after the preceding action-design amendment. Cross-record references: [P2-0 §15](../p2-0-contracts-and-acceptance.md) and [Phase 2 §18](../phase-2-specification-and-plan.md). This dated amendment takes precedence for the policy below; earlier proposals, pending statements and verification evidence remain historical. Approval of the procedure does not resolve its detailed implementation choices.

### Approved procedure

- **Secure invocation:** either co-founder may initiate the dedicated Emergency Suspend Admin action against the other founder when compromise is suspected. The acting founder must use their own account, provide a reason/category and explicit confirmation, and satisfy recent authentication appropriate to the environment before the sensitive action. The exact freshness interval remains pending. Routine mutual approval must not delay protective suspension. MFA is waived only for strictly local development on the development machine, with development data and no public tunnel or shared remote exposure; shared/remote test and production retain admin MFA.
- **Authoritative enforcement:** DRIP must change authoritative admin-grant/session state in PostgreSQL, confirm suspension and reject subsequent protected API requests through DRIP-side authorization and session/grant enforcement. Token expiry alone is insufficient; Redis is not authoritative. Never report successful suspension before the authoritative change is confirmed. Preserve the affected founder's customer account, wishlist, personal data and unrelated customer access; protective authority does not confer new privileges or bypass ordinary grant approval.
- **Suspension audit:** record the initiating founder, affected account, timestamp, reason/category, action, result and subsequent review/restoration outcome. Never log authentication secrets, including passwords, tokens or recovery codes, or include them in notifications.
- **Notification and partial failure:** attempt to notify both founders after the protective action. Track suspension status separately from notification status: confirmed suspension with failed or pending notification remains a **successful protective suspension**, while notification is reported separately as failed or pending. Notification failure must never roll back or undo suspension. Record notification attempts and outcomes, and require a retry or documented fallback process; its mechanism is still pending. Never claim successful notification delivery without supporting confirmation.
- **Review and restoration:** review the suspected compromise and secure the affected identity before restoration. Revoke or invalidate old affected sessions as supported by the approved session design. Restoration requires approval from the other founder; the affected founder cannot approve their own restoration. Record the review, approval, restoration actor, timestamp and outcome. Explicitly restore only the necessary admin grant after required identity remediation and authentication assurance are satisfied, and establish fresh valid sessions where required. Never restore access automatically because time elapsed or a provider became reachable again.

The preceding partial-failure proposals are now qualified by this approved policy: do not present confirmed suspension as unsuccessful solely because notification failed or is pending. If the authoritative change is unconfirmed, do not claim suspension succeeded. This approval does not select exact UI wording or resolve uncertain/incomplete enforcement, audit-failure coordination, reconciliation or in-flight behavior.

### Pending implementation choices and gates

**C1 and D3 remain PARTIALLY OPEN.** Recent authentication is now required; only its exact interval and detailed assurance/implementation remain open. The review/remediation/other-founder-approval sequence is approved policy, not an implemented recovery runbook.

- **C1:** exact recent-authentication/freshness interval and remaining environment-specific security/assurance details.
- **C1/D3:** emergency-action interface, secure exposure/misuse protection and technical authorization implementation; detailed incident evidence handling and identity-remediation/restoration mechanics consistent with the approved sequence.
- **Notification design:** provider/service, channel, delivery configuration and guarantees, retry schedule and documented fallback mechanism, including independent verification. A retry or fallback process is required, but none is chosen or configured.
- **C4:** durable session/token enforcement, old-session invalidation, fresh-session establishment, in-flight requests and provider-side changes; unresolved failure/reconciliation mechanics.
- **C7:** audit retention, deletion and backup behavior.
- **D3:** actual founder identities, account mappings and formal authority/primary-backup designations; existing bootstrap and source-approver details remain open. No names, identifiers or credentials are invented.
- **Documentation review:** authentication implementation remains paused until applicable owner decisions, authority designations and the required documentation review gate are resolved. This amendment does not authorize implementation or close P2-0/P2-1. P2-B/OOTD remains separately gated.

Documentation only: no application code, UI, endpoints, permissions, database changes, migrations, tests, dependencies or runtime configuration are created. No users are provisioned; no Cognito, Google OAuth, AWS or notification services are configured; no services are started/stopped and no databases are accessed. No new software-test evidence is claimed.

