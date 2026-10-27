"""The composition root: every repository and service, built once and wired together.

Controllers reach these through `request.app.state.module` (see
`decorators/inject_module.py`), so a test can build an `AppModule` on whatever
database it likes and hand it to `create_app`.
"""

from __future__ import annotations

from app.database import neon
from app.modules.account.account_repository import AccountRepository
from app.modules.account.account_service import AccountService
from app.modules.agent import agent as agent_layer
from app.modules.agent.account_toolbox import AccountToolbox
from app.modules.auth.auth_service import AuthService
from app.modules.bill.bill_service import BillService
from app.modules.chain import vault_signer
from app.modules.limit.limit_service import LimitService
from app.modules.payment.bill_payment_service import BillPaymentService
from app.modules.payment.payment_service import PaymentService
from app.modules.plan.plan_service import PlanService
from app.modules.receipt.receipt_repository import ReceiptRepository
from app.modules.reminder.reminder_service import ReminderService
from app.modules.state.state_service import StateService
from app.modules.stub.stub_service import StubService
from app.modules.suggestion.suggestion_service import SuggestionService
from app.modules.telegram.identity_repository import IdentityRepository
from app.modules.telegram.telegram_service import TelegramService
from app.modules.telemetry.telemetry_repository import TelemetryRepository
from app.modules.telemetry.telemetry_service import TelemetryService
from app.modules.vending import vending
from app.modules.voice.voice_service import VoiceService
from app.modules.wallet.wallet_service import WalletService
from app.shared.services.api_config_service import ApiConfigService


class AppModule:
    def __init__(self, config: ApiConfigService, db: neon.Database) -> None:
        self.config = config
        self.db = db

        self.receipts = ReceiptRepository(db)
        self.account_repository = AccountRepository(db)
        self.readings = TelemetryRepository(db)
        self.identities = IdentityRepository(db)

        self.auth = AuthService(db)
        self.accounts = AccountService(self.auth, self.account_repository, self.receipts,
                                       self._build_agent)
        self.bills = BillService(self.accounts, self.account_repository, self.receipts)
        self.plans = PlanService()
        self.wallet = WalletService(self.accounts, self.receipts)
        self.limits = LimitService(self.accounts, self.wallet)
        self.telemetry = TelemetryService(self.readings, self.receipts)
        self.bill_payments = BillPaymentService(
            self.accounts, self.bills, self.wallet,
            PaymentService(self.receipts, vending.gateway_from_env()),
        )
        self.state = StateService(self.accounts, self.wallet, self.telemetry)
        self.suggestions = SuggestionService(self.accounts, self.wallet, self.telemetry,
                                             self.bill_payments)
        self.voice = VoiceService(self.accounts)
        self.telegram = TelegramService(config, db, self.identities, self.accounts)
        self.reminders = ReminderService(self.accounts, self.telegram)
        self.stub = StubService(config, self.accounts, self.account_repository,
                                self.receipts, self.readings, self.identities,
                                self.reminders)

    @classmethod
    def from_env(cls) -> "AppModule":
        """`DATABASE_URL` is required: accounts, wallets and receipts live there."""
        return cls(ApiConfigService.from_env(), neon.open_database())

    def _build_agent(self, account_id: str, limits: agent_layer.Limits) -> agent_layer.Agent:
        """An agent bound to one account's toolbox and caps."""
        return agent_layer.build_agent(AccountToolbox(account_id, self), limits,
                                       signer=vault_signer.signer_from_env())

