/**
 * The client half of the identity-ownership refusal contract.
 *
 * When account resolution is ambiguous the backend refuses rather than guessing
 * between candidate rows, and answers the quota path with one typed shape built by
 * `subscription_gating.account_conflict_response`. This module is the only place the
 * client recognises it.
 *
 * Why it is not folded into the generic error path: that path says "I couldn't
 * process your request", which reads as a transient fault and offers a retry. An
 * ownership refusal is not transient and retrying it cannot succeed, so the two
 * states have to stay distinguishable at the point the client decides what to show.
 *
 * Deliberately narrow — it matches on `type` alone, the contract's own discriminant.
 * Requiring `error` as well would couple the client to a second field and let a
 * benign backend rewording silently turn a conflict back into a generic error.
 */

/** Discriminant emitted by the backend refusal contract. */
export const ACCOUNT_CONFLICT_TYPE = "account_conflict";

/** Stable, non-identifying reason code carried alongside it. */
export const ACCOUNT_CONFLICT_ERROR = "ambiguous_account_ownership";

type MaybeChatResponse = { type?: string | null } | null | undefined;

/** True when a chat response is the ownership-refusal contract. */
export function isAccountConflictResponse(res: MaybeChatResponse): boolean {
    return !!res && res.type === ACCOUNT_CONFLICT_TYPE;
}
