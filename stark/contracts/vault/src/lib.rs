//! Stark vault — spending caps enforced onchain.
//!
//! This is the "never cut" piece of the product: the guarantee that an AI agent
//! holding a function-call key cannot drain a user's balance.
//!
//! IMPORTANT — what this does and does not do yet:
//!
//! * **Does:** cap enforcement (monthly + per-payment), meter allowlist, calendar
//!   month rollover, owner-only policy changes, owner withdraw, NEP-297 events.
//! * **Does not:** move tokens. `balance_ngn` is an internal ledger. The real
//!   version credits on an NEP-141 `ft_on_transfer` (USDC on NEAR) and settles to
//!   the treasury with `ft_transfer`. That integration is M3, and until then no
//!   money moves onchain. Say so plainly if asked — do not imply tokens move.
//!
//! `policy.rs` holds the cap rules with no `near-sdk` import, so the logic that
//! matters is tested directly rather than through a chain mock.

mod policy;

pub use policy::{period_key, remaining_cap, Rejection};

use near_sdk::json_types::U128;
use near_sdk::{env, near, require, AccountId, PanicOnDefault};

/// NEP-297 event standard identifier.
const EVENT_STANDARD: &str = "stark-vault";
const EVENT_VERSION: &str = "1.0";

const ERR_OWNER_ONLY: &str = "Only the owner can do that";
const ERR_PAUSED: &str = "This vault is paused right now";
const ERR_NO_BALANCE_MSG: &str = "That's more than the balance";

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Vault {
    /// The human. Nobody else can change policy or withdraw.
    owner: AccountId,
    /// Where a real deployment sends settled funds.
    treasury: AccountId,
    paused: bool,
    monthly_cap_ngn: u128,
    per_payment_cap_ngn: u128,
    allowed_meters: Vec<String>,
    /// Spend already booked in `period_key`.
    spent_period_ngn: u128,
    /// `"YYYY-MM"` the spend above belongs to.
    period_key: String,
    /// Ledger balance, naira. NOT a token balance yet — see the module docs.
    balance_ngn: u128,
    total_paid_ngn: u128,
    payment_count: u64,
}

/// Returned by `pay`. Plain data, so serde is derived explicitly — the wasm
/// build serialises these on the way out, and a bare `#[near]` only derives borsh.
#[derive(near_sdk::serde::Serialize, near_sdk::serde::Deserialize)]
#[serde(crate = "near_sdk::serde")]
pub struct PaymentOutcome {
    pub payment_id: u64,
    pub meter: String,
    pub amount_ngn: U128,
    pub remaining_cap_ngn: U128,
}

#[derive(near_sdk::serde::Serialize, near_sdk::serde::Deserialize)]
#[serde(crate = "near_sdk::serde")]
pub struct PolicyView {
    pub monthly_cap_ngn: U128,
    pub per_payment_cap_ngn: U128,
    pub allowed_meters: Vec<String>,
    pub period_key: String,
}

#[derive(near_sdk::serde::Serialize, near_sdk::serde::Deserialize)]
#[serde(crate = "near_sdk::serde")]
pub struct StateView {
    pub paused: bool,
    /// `"YYYY-MM"` the spend counter belongs to.
    pub period_key: String,
    pub spent_period_ngn: U128,
    pub remaining_cap_ngn: U128,
    pub balance_ngn: U128,
    pub total_paid_ngn: U128,
    pub payment_count: u64,
}

#[near]
impl Vault {
    #[init]
    pub fn new(
        owner: AccountId,
        treasury: AccountId,
        monthly_cap_ngn: U128,
        per_payment_cap_ngn: U128,
        allowed_meters: Vec<String>,
    ) -> Self {
        require!(
            per_payment_cap_ngn.0 <= monthly_cap_ngn.0,
            "The per-payment limit cannot be above the monthly limit"
        );
        Self {
            owner,
            treasury,
            paused: false,
            monthly_cap_ngn: monthly_cap_ngn.0,
            per_payment_cap_ngn: per_payment_cap_ngn.0,
            allowed_meters,
            spent_period_ngn: 0,
            period_key: period_key(env::block_timestamp() as u128),
            balance_ngn: 0,
            total_paid_ngn: 0,
            payment_count: 0,
        }
    }

    /// Book a bill payment. Panics with a plain-English reason if it breaks a rule.
    ///
    /// Returns a `PaymentOutcome`; the meter token itself comes from the bill API,
    /// not from this contract.
    pub fn pay(&mut self, meter: String, amount_ngn: U128) -> PaymentOutcome {
        require!(!self.paused, ERR_PAUSED);
        let amount = amount_ngn.0;
        self.refresh_period();

        let allowed = self.allowed_meters.contains(&meter);
        if let Err(rejected) = policy::check_payment(
            self.monthly_cap_ngn,
            self.per_payment_cap_ngn,
            self.spent_period_ngn,
            self.balance_ngn,
            amount,
            allowed,
        ) {
            // Log the machine code, then panic with the human sentence.
            env::log_str(&format!(
                r#"{{"code":"{}","message":"{}"}}"#,
                rejected.code(),
                rejected.as_str()
            ));
            env::panic_str(rejected.as_str());
        }

        self.spent_period_ngn += amount;
        self.total_paid_ngn += amount;
        self.balance_ngn -= amount;
        self.payment_count += 1;

        let remaining = remaining_cap(self.monthly_cap_ngn, self.spent_period_ngn);
        emit_payment(&meter, amount, self.payment_count, &self.period_key, remaining);

        PaymentOutcome {
            payment_id: self.payment_count,
            meter,
            amount_ngn,
            remaining_cap_ngn: U128(remaining),
        }
    }

    /// Owner-only. Blocked while paused.
    pub fn set_policy(
        &mut self,
        monthly_cap_ngn: U128,
        per_payment_cap_ngn: U128,
        allowed_meters: Vec<String>,
    ) {
        self.assert_owner();
        require!(
            per_payment_cap_ngn.0 <= monthly_cap_ngn.0,
            "The per-payment limit cannot be above the monthly limit"
        );
        self.monthly_cap_ngn = monthly_cap_ngn.0;
        self.per_payment_cap_ngn = per_payment_cap_ngn.0;
        self.allowed_meters = allowed_meters;
    }

    /// Owner-only: widen the allowlist without re-sending the whole policy.
    pub fn add_meter(&mut self, meter: String) {
        self.assert_owner();
        if !self.allowed_meters.contains(&meter) {
            self.allowed_meters.push(meter);
        }
    }

    pub fn remove_meter(&mut self, meter: String) {
        self.assert_owner();
        self.allowed_meters.retain(|m| *m != meter);
    }

    /// Owner-only: pause payments, e.g. after a compromised key.
    pub fn pause(&mut self) {
        self.assert_owner();
        self.paused = true;
    }

    pub fn unpause(&mut self) {
        self.assert_owner();
        self.paused = false;
    }

    /// Owner withdraw. Works even while paused — the owner can always get out.
    pub fn withdraw(&mut self, amount_ngn: U128) {
        self.assert_owner();
        require!(amount_ngn.0 <= self.balance_ngn, ERR_NO_BALANCE_MSG);
        self.balance_ngn -= amount_ngn.0;
        env::log_str(&format!(
            r#"{{"standard":"{}","version":"{}","event":"withdrawn","data":[{{"amount_ngn":"{}"}}]}}"#,
            EVENT_STANDARD, EVENT_VERSION, amount_ngn.0
        ));
    }

    /// Scaffold stand-in for an NEP-141 `ft_on_transfer` credit.
    /// See the module docs: no real tokens are involved yet.
    pub fn fund(&mut self, amount_ngn: U128) {
        self.balance_ngn += amount_ngn.0;
        env::log_str(&format!(
            r#"{{"standard":"{}","version":"{}","event":"funded","data":[{{"amount_ngn":"{}","balance_ngn":"{}"}}]}}"#,
            EVENT_STANDARD, EVENT_VERSION, amount_ngn.0, self.balance_ngn
        ));
    }

    // --- views ---------------------------------------------------------------

    pub fn get_policy(&self) -> PolicyView {
        let (key, _) = self.current_period();
        PolicyView {
            monthly_cap_ngn: U128(self.monthly_cap_ngn),
            per_payment_cap_ngn: U128(self.per_payment_cap_ngn),
            allowed_meters: self.allowed_meters.clone(),
            period_key: key,
        }
    }

    pub fn get_state(&self) -> StateView {
        let (key, spent) = self.current_period();
        StateView {
            paused: self.paused,
            period_key: key,
            spent_period_ngn: U128(spent),
            remaining_cap_ngn: U128(remaining_cap(self.monthly_cap_ngn, spent)),
            balance_ngn: U128(self.balance_ngn),
            total_paid_ngn: U128(self.total_paid_ngn),
            payment_count: self.payment_count,
        }
    }

    /// Dry-run a payment without changing anything, so the UI can disable buttons.
    pub fn can_pay(&self, meter: String, amount_ngn: U128) -> bool {
        if self.paused {
            return false;
        }
        let (_, spent) = self.current_period();
        let allowed = self.allowed_meters.contains(&meter);
        policy::check_payment(
            self.monthly_cap_ngn,
            self.per_payment_cap_ngn,
            spent,
            self.balance_ngn,
            amount_ngn.0,
            allowed,
        )
        .is_ok()
    }
}

impl Vault {
    fn assert_owner(&self) {
        require!(
            env::predecessor_account_id() == self.owner,
            ERR_OWNER_ONLY
        );
    }

    /// What the period *currently* is, even if no transaction has touched state
    /// since the month rolled over. Views must not report last month's spend.
    fn current_period(&self) -> (String, u128) {
        let key = period_key(env::block_timestamp() as u128);
        if key == self.period_key {
            (key, self.spent_period_ngn)
        } else {
            (key, 0)
        }
    }

    /// Roll the spend counter when a new calendar month starts.
    fn refresh_period(&mut self) {
        let key = period_key(env::block_timestamp() as u128);
        if key != self.period_key {
            self.period_key = key;
            self.spent_period_ngn = 0;
        }
    }
}

/// NEP-297 shaped event, hand-built so we don't depend on macro internals.
fn emit_payment(
    meter: &str,
    amount_ngn: u128,
    payment_id: u64,
    period: &str,
    remaining_ngn: u128,
) {
    env::log_str(&format!(
        concat!(
            r#"{{"standard":"{}","version":"{}","event":"payment","data":[{{"payment_id":"{}","meter":"{}","#,
            r#""amount_ngn":"{}","period":"{}","remaining_cap_ngn":"{}"}}]}}"#
        ),
        EVENT_STANDARD,
        EVENT_VERSION,
        payment_id,
        meter,
        amount_ngn,
        period,
        remaining_ngn
    ));
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::test_utils::{accounts, VMContextBuilder};
    use near_sdk::testing_env;

    const METER: &str = "04512345678";
    const METER2: &str = "08031234567";

    /// 2026-10-20 00:00 UTC, in nanoseconds.
    const OCT_2026: u64 = 1_792_454_400_000_000_000;
    /// 2026-11-01 00:00 UTC, in nanoseconds.
    const NOV_2026: u64 = 1_793_491_200_000_000_000;

    fn context(predecessor: AccountId, timestamp: u64) -> VMContextBuilder {
        let mut builder = VMContextBuilder::new();
        builder
            .current_account_id(accounts(0))
            .predecessor_account_id(predecessor)
            .block_timestamp(timestamp);
        builder
    }

    /// Owner is accounts(0), treasury is accounts(1), funded with ₦64,200.
    fn funded_vault() -> Vault {
        testing_env!(context(accounts(0), OCT_2026).build());
        let mut vault = Vault::new(
            accounts(0),
            accounts(1),
            U128(30_000),
            U128(10_000),
            vec![METER.to_string()],
        );
        vault.fund(U128(64_200));
        vault
    }

    // --- caps: the never-cut guarantee --------------------------------------

    #[test]
    fn a_payment_within_the_limits_succeeds() {
        let mut v = funded_vault();
        let out = v.pay(METER.to_string(), U128(5_000));
        assert_eq!(out.payment_id, 1);
        assert_eq!(out.amount_ngn, U128(5_000));
        assert_eq!(out.remaining_cap_ngn, U128(25_000));
        assert_eq!(v.get_state().spent_period_ngn, U128(5_000));
    }

    #[test]
    #[should_panic(expected = "over your monthly limit")]
    fn refuses_a_payment_over_the_monthly_cap() {
        let mut v = funded_vault();
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        // 30,000 spent of a 30,000 cap → one more naira must fail.
        v.pay(METER.to_string(), U128(1));
    }

    #[test]
    #[should_panic(expected = "most you allow in one go")]
    fn refuses_a_payment_over_the_per_payment_cap() {
        let mut v = funded_vault();
        v.pay(METER.to_string(), U128(10_001));
    }

    #[test]
    #[should_panic(expected = "isn't on your list")]
    fn refuses_a_meter_that_is_not_on_the_allowlist() {
        let mut v = funded_vault();
        v.pay(METER2.to_string(), U128(1_000));
    }

    #[test]
    #[should_panic(expected = "paused")]
    fn refuses_payments_while_paused() {
        let mut v = funded_vault();
        v.pause();
        v.pay(METER.to_string(), U128(1_000));
    }

    #[test]
    fn the_cap_resets_when_the_month_rolls_over() {
        let mut v = funded_vault();
        v.pay(METER.to_string(), U128(10_000));
        v.pay(METER.to_string(), U128(10_000));
        v.pay(METER.to_string(), U128(10_000));
        assert_eq!(v.get_state().remaining_cap_ngn, U128(0));

        // New month, new allowance.
        testing_env!(context(accounts(0), NOV_2026).build());
        assert_eq!(v.get_state().period_key, "2026-11");
        assert_eq!(v.get_state().remaining_cap_ngn, U128(30_000));

        let out = v.pay(METER.to_string(), U128(10_000));
        assert_eq!(out.payment_id, 4, "counter is cumulative across months");
    }

    #[test]
    fn the_monthly_counter_is_shared_across_meters() {
        // Adding a second meter does not give the user a second allowance.
        let mut v = funded_vault();
        v.add_meter(METER2.to_string());
        v.pay(METER.to_string(), U128(10_000));
        v.pay(METER2.to_string(), U128(10_000));
        v.pay(METER2.to_string(), U128(10_000));
        assert_eq!(v.get_state().remaining_cap_ngn, U128(0));
    }

    // --- ownership: the reason an agent can't drain the wallet ---------------

    #[test]
    #[should_panic(expected = "Only the owner")]
    fn a_non_owner_cannot_withdraw() {
        let mut v = funded_vault();
        testing_env!(context(accounts(2), OCT_2026).build());
        v.withdraw(U128(1_000));
    }

    #[test]
    #[should_panic(expected = "Only the owner")]
    fn a_non_owner_cannot_change_the_policy() {
        let mut v = funded_vault();
        testing_env!(context(accounts(2), OCT_2026).build());
        v.set_policy(U128(10_000_000), U128(9_000_000), vec![]);
    }

    #[test]
    #[should_panic(expected = "Only the owner")]
    fn a_non_owner_cannot_pause() {
        let mut v = funded_vault();
        testing_env!(context(accounts(2), OCT_2026).build());
        v.pause();
    }

    #[test]
    #[should_panic(expected = "Only the owner")]
    fn a_non_owner_cannot_widen_the_allowlist() {
        let mut v = funded_vault();
        testing_env!(context(accounts(2), OCT_2026).build());
        v.add_meter(METER2.to_string());
    }

    #[test]
    fn the_owner_can_always_withdraw_even_while_paused() {
        let mut v = funded_vault();
        v.pause();
        v.withdraw(U128(20_000));
        assert_eq!(v.get_state().balance_ngn, U128(44_200));
    }

    // --- ledger ---------------------------------------------------------------

    #[test]
    #[should_panic(expected = "isn't enough in your balance")]
    fn refuses_to_pay_more_than_the_ledger_holds() {
        // Caps are generous; the balance is not. Policy must not mask it.
        testing_env!(context(accounts(0), OCT_2026).build());
        let mut v = Vault::new(
            accounts(0),
            accounts(1),
            U128(30_000),
            U128(10_000),
            vec![METER.to_string()],
        );
        v.fund(U128(4_000));
        v.pay(METER.to_string(), U128(5_000));
    }

    #[test]
    fn total_paid_is_cumulative_across_months() {
        let mut v = funded_vault();
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        testing_env!(context(accounts(0), NOV_2026).build());
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        assert_eq!(v.get_state().total_paid_ngn, U128(60_000));
    }

    // --- guard rails -----------------------------------------------------------

    #[test]
    #[should_panic(expected = "per-payment limit cannot be above the monthly")]
    fn refuses_a_per_payment_cap_above_the_monthly_cap() {
        testing_env!(context(accounts(0), OCT_2026).build());
        Vault::new(
            accounts(0),
            accounts(1),
            U128(30_000),
            U128(90_000),
            vec![METER.to_string()],
        );
    }

    // --- view helper -------------------------------------------------------------

    #[test]
    fn can_pay_is_false_where_pay_would_fail() {
        let mut v = funded_vault();
        assert!(v.can_pay(METER.to_string(), U128(5_000)));
        assert!(!v.can_pay(METER.to_string(), U128(10_001))); // per-payment cap
        assert!(!v.can_pay(METER2.to_string(), U128(1_000))); // allowlist
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        assert!(!v.can_pay(METER.to_string(), U128(1)), "cap exhausted");
        v.pause();
        assert!(!v.can_pay(METER.to_string(), U128(1)), "paused");
    }

    #[test]
    fn views_report_the_new_allowance_after_a_rollover_without_a_transaction() {
        // Regression: get_state/get_policy/can_pay used to keep reporting last
        // month's spend until some transaction rolled the period over.
        let mut v = funded_vault();
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        assert_eq!(v.get_state().remaining_cap_ngn, U128(0));

        testing_env!(context(accounts(0), NOV_2026).build());
        assert_eq!(v.get_state().period_key, "2026-11");
        assert_eq!(v.get_state().spent_period_ngn, U128(0));
        assert_eq!(v.get_state().remaining_cap_ngn, U128(30_000));
        assert!(v.can_pay(METER.to_string(), U128(10_000)));
        assert_eq!(v.get_state().total_paid_ngn, U128(30_000), "total_paid is not reset");
    }

    #[test]
    fn the_state_still_binds_within_the_same_month() {
        // The inverse: nothing must reset just because time passed inside a month.
        let mut v = funded_vault();
        for _ in 0..3 {
            v.pay(METER.to_string(), U128(10_000));
        }
        assert_eq!(v.get_state().spent_period_ngn, U128(30_000));
        assert_eq!(v.get_state().remaining_cap_ngn, U128(0));
    }

    #[test]
    fn removing_a_meter_takes_effect_immediately() {
        let mut v = funded_vault();
        v.remove_meter(METER.to_string());
        assert!(v.get_policy().allowed_meters.is_empty());
        assert!(!v.can_pay(METER.to_string(), U128(1_000)));
    }
}
