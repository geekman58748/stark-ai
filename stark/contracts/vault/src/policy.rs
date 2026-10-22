//! Pure policy rules for the Stark vault.
//!
//! Nothing here imports `near-sdk`, deliberately: the caps and allowlist are the
//! part of the product that has to be *correct*, so they are tested directly with
//! no chain mock, no env, no network. `lib.rs` applies these rules to state.

/// Why a payment was refused. `as_str()` is what the user hears — no jargon.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Rejection {
    ZeroAmount,
    ExceedsPerPayment { amount_ngn: u128, cap_ngn: u128 },
    ExceedsMonthly { amount_ngn: u128, remaining_ngn: u128 },
    MeterNotAllowed,
    InsufficientBalance { need_ngn: u128, have_ngn: u128 },
}

impl Rejection {
    /// Plain-English line the agent can say out loud.
    pub fn as_str(&self) -> &'static str {
        match self {
            Rejection::ZeroAmount => "That amount needs to be above zero.",
            Rejection::ExceedsPerPayment { .. } => {
                "That's over the most you allow in one go."
            }
            Rejection::ExceedsMonthly { .. } => {
                "That would go over your monthly limit."
            }
            Rejection::MeterNotAllowed => {
                "That meter isn't on your list. Add it first, or pick another one."
            }
            Rejection::InsufficientBalance { .. } => {
                "There isn't enough in your balance for that."
            }
        }
    }

    /// Stable machine code. The frontend branches on this, never on `as_str`.
    pub fn code(&self) -> &'static str {
        match self {
            Rejection::ZeroAmount => "bad_amount",
            Rejection::ExceedsPerPayment { .. } => "over_per_payment_cap",
            Rejection::ExceedsMonthly { .. } => "over_cap",
            Rejection::MeterNotAllowed => "meter_not_allowed",
            Rejection::InsufficientBalance { .. } => "insufficient_balance",
        }
    }
}

/// Decide whether a payment is allowed. The order is deliberate:
///
/// 1. per-payment cap — cheapest, most specific refusal
/// 2. monthly cap — the headline safety guarantee
/// 3. allowlist — never pay a meter the owner didn't name
/// 4. balance — checked last, so a policy problem is reported as policy, not money
pub fn check_payment(
    monthly_cap_ngn: u128,
    per_payment_cap_ngn: u128,
    spent_this_period_ngn: u128,
    balance_ngn: u128,
    amount_ngn: u128,
    meter_allowed: bool,
) -> Result<(), Rejection> {
    if amount_ngn == 0 {
        return Err(Rejection::ZeroAmount);
    }
    if amount_ngn > per_payment_cap_ngn {
        return Err(Rejection::ExceedsPerPayment {
            amount_ngn,
            cap_ngn: per_payment_cap_ngn,
        });
    }
    // checked_add, not saturating: if spent + amount overflows u128 it is
    // certainly above any representable cap, so it must be refused rather
    // than silently clamped.
    let fits_in_monthly_cap = spent_this_period_ngn
        .checked_add(amount_ngn)
        .is_some_and(|total| total <= monthly_cap_ngn);
    if !fits_in_monthly_cap {
        return Err(Rejection::ExceedsMonthly {
            amount_ngn,
            remaining_ngn: monthly_cap_ngn.saturating_sub(spent_this_period_ngn),
        });
    }
    if !meter_allowed {
        return Err(Rejection::MeterNotAllowed);
    }
    if amount_ngn > balance_ngn {
        return Err(Rejection::InsufficientBalance {
            need_ngn: amount_ngn,
            have_ngn: balance_ngn,
        });
    }
    Ok(())
}

/// Remaining allowance for the current period.
pub fn remaining_cap(monthly_cap_ngn: u128, spent_this_period_ngn: u128) -> u128 {
    monthly_cap_ngn.saturating_sub(spent_this_period_ngn)
}

/// `"YYYY-MM"` for a block timestamp. This is what makes the cap *monthly*.
///
/// Epoch days → (year, month) via Howard Hinnant's civil calendar algorithm —
/// integer-only, no float, no crate.
pub fn period_key(timestamp_nanos: u128) -> String {
    let seconds = timestamp_nanos / 1_000_000_000;
    let days = (seconds / 86_400) as i64;
    let (year, month) = civil_from_days(days);
    format!("{:04}-{:02}", year, month)
}

fn civil_from_days(z: i64) -> (i64, u32) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u64; // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365; // [0, 399]
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); // [0, 365]
    let mp = (5 * doy + 2) / 153; // [0, 11]
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m)
}

#[cfg(test)]
mod tests {
    use super::*;

    const MONTHLY: u128 = 30_000;
    const PER_PAY: u128 = 10_000;

    fn ok(spent: u128, balance: u128, amount: u128, allowed: bool) -> Result<(), Rejection> {
        check_payment(MONTHLY, PER_PAY, spent, balance, amount, allowed)
    }

    #[test]
    fn allows_a_payment_within_every_limit() {
        assert_eq!(ok(0, 64_200, 5_000, true), Ok(()));
    }

    #[test]
    fn rejects_zero_amount() {
        assert_eq!(ok(0, 64_200, 0, true), Err(Rejection::ZeroAmount));
    }

    #[test]
    fn rejects_over_per_payment_cap() {
        assert_eq!(
            ok(0, 64_200, 10_001, true),
            Err(Rejection::ExceedsPerPayment {
                amount_ngn: 10_001,
                cap_ngn: PER_PAY,
            })
        );
    }

    #[test]
    fn allows_exactly_the_per_payment_cap() {
        assert_eq!(ok(0, 64_200, 10_000, true), Ok(()));
    }

    #[test]
    fn rejects_over_monthly_cap() {
        assert_eq!(
            ok(25_000, 64_200, 6_000, true),
            Err(Rejection::ExceedsMonthly {
                amount_ngn: 6_000,
                remaining_ngn: 5_000,
            })
        );
    }

    #[test]
    fn allows_exactly_the_monthly_cap() {
        // 25,000 already spent of 30,000 → 5,000 left, and 5,000 is the ask.
        assert_eq!(ok(25_000, 64_200, 5_000, true), Ok(()));
    }

    #[test]
    fn rejects_a_payment_on_an_unlisted_meter() {
        assert_eq!(ok(0, 64_200, 1_000, false), Err(Rejection::MeterNotAllowed));
    }

    #[test]
    fn policy_violation_reports_before_balance_problem() {
        // Over cap AND broke: the user should hear about the cap, not the money.
        let err = ok(29_000, 100, 9_000, false).unwrap_err();
        assert_eq!(err.code(), "over_cap");
    }

    #[test]
    fn allowlist_checked_before_balance() {
        let err = check_payment(MONTHLY, PER_PAY, 0, 100, 1_000, false).unwrap_err();
        assert_eq!(err.code(), "meter_not_allowed");
    }

    #[test]
    fn rejects_when_balance_is_short() {
        assert_eq!(
            ok(0, 4_000, 5_000, true),
            Err(Rejection::InsufficientBalance {
                need_ngn: 5_000,
                have_ngn: 4_000,
            })
        );
    }

    #[test]
    fn does_not_overflow_when_spent_is_high() {
        // Regression: a wrapping add here would let a huge payment slip past the
        // cap, so the overflow must be treated as "over the cap".
        let spent = u128::MAX - 10;
        let err = check_payment(u128::MAX, u128::MAX, spent, u128::MAX, 1_000, true)
            .unwrap_err();
        assert_eq!(
            err,
            Rejection::ExceedsMonthly {
                amount_ngn: 1_000,
                remaining_ngn: 10,
            }
        );
    }

    #[test]
    fn a_sum_that_fits_exactly_at_the_cap_is_allowed() {
        assert_eq!(
            check_payment(30_000, 30_000, 29_000, 99_999, 1_000, true),
            Ok(())
        );
    }

    #[test]
    fn remaining_cap_never_goes_negative() {
        assert_eq!(remaining_cap(30_000, 12_400), 17_600);
        assert_eq!(remaining_cap(30_000, 99_999), 0);
    }

    #[test]
    fn messages_have_no_crypto_jargon() {
        // Ground rule: no "vault", no "USDC", no wallet addresses in user copy.
        for rej in [
            Rejection::ZeroAmount,
            Rejection::ExceedsPerPayment { amount_ngn: 1, cap_ngn: 2 },
            Rejection::ExceedsMonthly { amount_ngn: 1, remaining_ngn: 2 },
            Rejection::MeterNotAllowed,
            Rejection::InsufficientBalance { need_ngn: 1, have_ngn: 2 },
        ] {
            let msg = rej.as_str().to_lowercase();
            for banned in ["vault", "usdc", "usdt", "onchain", "blockchain", "contract"] {
                assert!(
                    !msg.contains(banned),
                    "user-facing message leaked '{}': {}",
                    banned,
                    rej.as_str()
                );
            }
        }
    }

    /// 2026-10-20 00:00 UTC = epoch 1_792_454_400 s.
    const OCT_20_2026: u128 = 1_792_454_400_000_000_000;
    /// 2026-10-31 23:59:59 UTC = epoch 1_793_491_199 s.
    const OCT_31_2026_LAST_SEC: u128 = 1_793_491_199_000_000_000;
    /// 2026-11-01 00:00:00 UTC = epoch 1_793_491_200 s.
    const NOV_1_2026: u128 = 1_793_491_200_000_000_000;

    #[test]
    fn period_key_is_a_calendar_month() {
        assert_eq!(period_key(OCT_20_2026), "2026-10");
    }

    #[test]
    fn period_key_rolls_over_exactly_at_the_month_boundary() {
        // One second apart: the cap must reset at midnight UTC on the 1st.
        assert_eq!(period_key(OCT_31_2026_LAST_SEC), "2026-10");
        assert_eq!(period_key(NOV_1_2026), "2026-11");
    }

    #[test]
    fn period_key_handles_leap_day() {
        // 2024-02-29 12:00 UTC = epoch 1_709_208_000 s. Feb has 29 days in 2024.
        let leap = 1_709_208_000u128 * 1_000_000_000;
        assert_eq!(period_key(leap), "2024-02");
    }

    #[test]
    fn civil_from_days_known_dates() {
        assert_eq!(civil_from_days(0), (1970, 1)); // epoch
        assert_eq!(civil_from_days(365), (1971, 1)); // non-leap year
        assert_eq!(civil_from_days(19_723), (2024, 1)); // 2024-01-01
        assert_eq!(civil_from_days(19_782), (2024, 2)); // 2024-02-29 (leap day)
        assert_eq!(civil_from_days(19_905), (2024, 7)); // 2024-07-01
    }

    #[test]
    fn unique_error_codes_for_the_frontend() {
        let codes = [
            Rejection::ZeroAmount.code(),
            Rejection::ExceedsPerPayment { amount_ngn: 1, cap_ngn: 2 }.code(),
            Rejection::ExceedsMonthly { amount_ngn: 1, remaining_ngn: 2 }.code(),
            Rejection::MeterNotAllowed.code(),
            Rejection::InsufficientBalance { need_ngn: 1, have_ngn: 2 }.code(),
        ];
        let mut sorted = codes.to_vec();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), codes.len(), "duplicate error codes");
    }
}
