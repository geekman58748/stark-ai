"""Stark's agent layer: tools, routing, policy gate and the model loop.

This is M2. The agent takes what the user said, lets a model choose tool calls,
runs them under the vault's rules, and returns a sentence that can be spoken.

Two model backends, one loop:

- `FakeModel` — deterministic, no key, no network. Used by the stub server and by
  every test. It decides from regexes, but emits exactly the same tool-call
  envelope a real model does, so the loop, the tools and the policy gate are the
  real thing.
- `NearAiModel` — the real thing, POSTing to NEAR AI's OpenAI-compatible
  `/v1/chat/completions`. Needs `NEAR_AI_API_KEY`. **Not exercised here** — no key
  existed when this was written. Treat its request/response parsing as unproven.

The safety property that matters: the policy gate is enforced in `_run_tool`, not
by asking the model nicely. A model that hallucinates a ₦40,000 payment gets a
refusal and no signature.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import policy as policy_rules

# The amount used when the user says "top it up" without naming a figure.
# ₦5,000 is the design's own sample payment and exactly the per-payment cap.
DEFAULT_AMOUNT_NGN = 5_000

NEAR_AI_BASE = os.environ.get("NEAR_AI_BASE_URL") or "https://cloud-api.near.ai"
# On NEAR's own fleet (Private TEE) and tool-capable. `openai/gpt-5-nano` is
# Incognito (no end-to-end TEE) and was `is_ready: false` when checked 2026-10-22.
NEAR_AI_MODEL = os.environ.get("NEAR_AI_MODEL") or "Qwen/Qwen3.8-27B"

SYSTEM_PROMPT = """You are Stark, a calm assistant that pays household bills.

Rules:
- Money is Nigerian naira, written like ₦5,000. Never mention crypto, wallets,
  tokens, chains or contracts.
- Read before you act. Use get_state or list_bills rather than guessing numbers.
- To pay, call pay_bill. The app enforces the user's limits itself; if it refuses,
  say the reason plainly and do not try a different amount to sneak past it.
- A payment is only done when the tool returns a token or status "delivered".
  "pending" means it is still going through — say so, and never claim it is done.
- Never invent a meter token, a balance or a receipt. Only repeat what a tool gave you.
- Reply in one or two short sentences, written to be read aloud.
- Amounts and meter numbers are read out digit by digit by the voice, so spell the
  number out in full.
"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_state",
            "description": (
                "Read the wallet balance, the monthly limit, how much is spent, and "
                "how many electricity units and days are left. Call this before "
                "answering any question about money or usage."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_bills",
            "description": (
                "List the saved bills (electricity, airtime, data, TV, internet, water) "
                "with their ids, labels and references."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_activity",
            "description": "The most recent payments, newest first.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pay_bill",
            "description": (
                "Pay a saved bill. Only call this when the user clearly asked to pay. "
                "The amount is in whole naira. If the user did not name an amount, use the "
                "bill's plan price when it has one, otherwise "
                f"{DEFAULT_AMOUNT_NGN}, and say which. A plan costs its own price. "
                "The app checks the user's limits before anything is charged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_id": {
                        "type": "string",
                        "description": "Id from list_bills. Empty means the main electricity meter.",
                    },
                    "amount_ngn": {
                        "type": "integer",
                        "description": "Whole naira, e.g. 5000.",
                    },
                },
                "required": ["amount_ngn"],
                "additionalProperties": False,
            },
        },
    },
]


# --- model interface ---------------------------------------------------------


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }


@dataclass
class ModelTurn:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def assistant_message(self) -> dict:
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [call.as_dict() for call in self.tool_calls],
        }


class Model(Protocol):
    name: str

    def turn(self, messages: list[dict], tools: list[dict]) -> ModelTurn: ...


# --- amount parsing ----------------------------------------------------------


_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def parse_amount(text: str) -> int | None:
    """Pull a naira amount out of what the user said.

    Handles "₦5,000", "5000", "5k", "1.5k" and spoken numbers up to the
    thousands ("five thousand", "two thousand five hundred"). Returns `None`
    when no amount was named, which is the signal to use the default.
    """
    heard = text.lower().replace(",", "").replace("₦", " ").replace("naira", " ")

    suffixed = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b", heard)
    if suffixed:
        return int(round(float(suffixed.group(1)) * 1000))

    digits = re.search(r"\b(\d{1,9})\b", heard)
    if digits:
        return int(digits.group(1))

    words = re.findall(r"[a-z]+", heard)
    total = 0
    current = 0
    seen = False
    for word in words:
        if word in _ONES:
            current += _ONES[word]
            seen = True
        elif word in _TENS:
            current += _TENS[word]
            seen = True
        elif word == "hundred":
            current = max(current, 1) * 100
            seen = True
        elif word == "thousand":
            total += max(current, 1) * 1000
            current = 0
            seen = True
        elif seen and word not in ("and",):
            # A new unrelated word after a number ends the amount.
            break
    amount = total + current
    return amount if seen and amount > 0 else None


# --- fake model --------------------------------------------------------------


_PAY_RE = re.compile(r"\b(top\s*(it\s*)?up|topup|buy|pay|recharge|send)\b")
_BILLS_RE = re.compile(r"\b(my\s+)?bills\b")
_ACTIVITY_RE = re.compile(r"\b(activity|history|recent|last payment|receipts?)\b")
_STATE_RE = re.compile(
    r"\b(balance|unit|units|how much|left|spend|spent|bill)\b"
)
_METER_RE = re.compile(r"\b(light|lights|electric|electricity|meter|nepa|prepaid|units?)\b")
# Naming a product that is not saved must not fall through to whatever is first.
_PRODUCT_RE = re.compile(
    r"\b(data|airtime|tv|cable|dstv|gotv|startimes|showmax|water|internet|subscription)\b"
)


def _label_match(bills: list[dict], heard: str) -> dict | None:
    for bill in bills:
        labels = (bill.get("label", ""), bill.get("provider", ""), bill.get("kind", ""))
        words = {w for label in labels for w in re.findall(r"[a-z]+", label.lower())
                 if len(w) > 2}
        if words and any(word in heard for word in words):
            return bill
    return None


def _choose_bill(bills: list[dict], user_text: str) -> dict | None:
    """Which bill a payment is for, as a careful model would infer it.

    Naming the light or the meter means the electricity bill and nothing else, and
    naming a product that is not saved means **no** bill — paying for something
    else because it happened to be first in the list would be a real mistake.
    """
    if not bills:
        return None
    heard = user_text.lower()
    if _METER_RE.search(heard):
        return next((b for b in bills if b.get("kind") == "electricity"), None)

    matched = _label_match(bills, heard)
    if matched is not None:
        return matched
    if _PRODUCT_RE.search(heard):
        return None
    return bills[0]


def _default_amount(bill: dict) -> int:
    """A plan-priced bill costs what the plan costs, not the sample ₦5,000."""
    price = bill.get("plan_price_ngn")
    return int(price) if isinstance(price, int) and price > 0 else DEFAULT_AMOUNT_NGN


class FakeModel:
    """Deterministic stand-in for the LLM.

    It classifies intent with regexes, but everything downstream — tool schema,
    tool routing, the policy gate, the reply payload — is exactly what the real
    model drives. That is the point: the loop is real, only the language model
    is fake.
    """

    name = "fake"

    def turn(self, messages: list[dict], tools: list[dict]) -> ModelTurn:
        last = messages[-1]
        user_text = self._last_user_text(messages)

        if last.get("role") == "tool":
            return self._after_tool(last, user_text)

        if last.get("role") != "user":
            return ModelTurn(content="What would you like me to do?")

        heard = user_text.lower()
        if _ACTIVITY_RE.search(heard):
            return ModelTurn(tool_calls=[ToolCall("recent_activity", {})])
        if _PAY_RE.search(heard):
            # Read the bill list first, exactly as a careful model would.
            return ModelTurn(tool_calls=[ToolCall("list_bills", {})])
        if _BILLS_RE.search(heard):
            return ModelTurn(tool_calls=[ToolCall("list_bills", {})])
        if _STATE_RE.search(heard):
            return ModelTurn(tool_calls=[ToolCall("get_state", {})])
        return ModelTurn(
            content="I can check your bill or top it up. Which one?"
        )

    @staticmethod
    def _last_user_text(messages: list[dict]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content") or ""
        return ""

    def _after_tool(self, message: dict, user_text: str) -> ModelTurn:
        result = _loads(message.get("content"))
        name = message.get("name") or ""

        if name == "list_bills" and _PAY_RE.search(user_text.lower()):
            bills = result.get("data") or []
            if not bills:
                return ModelTurn(content="There are no bills saved yet.")
            chosen = _choose_bill(bills, user_text)
            if chosen is None:
                return ModelTurn(
                    content=(
                        "I don't have a bill saved for that. Add it and I'll pay it "
                        "next time."
                    )
                )
            amount = parse_amount(user_text)
            if amount is None:
                amount = _default_amount(chosen)
            return ModelTurn(
                tool_calls=[
                    ToolCall(
                        "pay_bill",
                        {"bill_id": (chosen or {}).get("id", ""),
                         "amount_ngn": amount},
                    )
                ]
            )

        if name == "get_state":
            data = result.get("data") or {}
            units = data.get("units_left")
            days = data.get("days_left")
            spoken = f"You've got ₦{data.get('balance_ngn', 0):,} in your wallet"
            if units is not None:
                spoken += f" and about {units:g} units left"
                if days is not None:
                    spoken += f" — roughly {days} days at this rate"
            return ModelTurn(content=spoken + ".")

        if name == "list_bills":
            bills = result.get("data") or []
            labels = [b.get("label", "a bill") for b in bills]
            if not labels:
                return ModelTurn(content="There are no bills saved yet.")
            joined = ", ".join(labels[:-1]) + f" and {labels[-1]}" if len(labels) > 1 else labels[0]
            return ModelTurn(content=f"You've got {len(labels)} bills set up: {joined}.")

        if name == "recent_activity":
            receipts = result.get("data") or []
            if not receipts:
                return ModelTurn(content="Nothing has been paid yet.")
            latest = receipts[0]
            return ModelTurn(
                content=(
                    f"Your last payment was ₦{latest.get('amount_ngn', 0):,} "
                    f"to {latest.get('bill_label', 'a bill')}."
                )
            )

        if name == "pay_bill":
            if not result.get("ok"):
                error = result.get("error") or {}
                return ModelTurn(
                    content=error.get("message") or "That payment didn't go through."
                )
            data = result.get("data") or {}
            amount = data.get("amount_ngn", 0)
            label = data.get("bill_label", "your bill")
            if data.get("status") == "pending":
                return ModelTurn(
                    content=(
                        f"₦{amount:,} for {label} is still going through. "
                        "I'll bring you the token as soon as it lands."
                    )
                )
            if data.get("token"):
                return ModelTurn(
                    content=(
                        f"Done — ₦{amount:,} paid to {label}. "
                        f"Your token is {data['token']}. "
                        "I've put it in your activity too."
                    )
                )
            return ModelTurn(content=f"Done — ₦{amount:,} paid to {label}.")

        return ModelTurn(content="I couldn't do that one. Want to try again?")


def _loads(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# --- NEAR AI model -----------------------------------------------------------


class NearAiModel:
    """NEAR AI's OpenAI-compatible chat endpoint.

    Unproven: written from the documented shape, never run with a key. The
    request/response handling is deliberately narrow — one POST, tool calls only.
    """

    name = "near-ai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = NEAR_AI_MODEL,
        base_url: str = NEAR_AI_BASE,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.environ.get("NEAR_AI_API_KEY")
        if not self.api_key:
            raise ValueError("NEAR_AI_API_KEY is not set")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def turn(self, messages: list[dict], tools: list[dict]) -> ModelTurn:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                body = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as err:
            try:
                detail = err.read().decode("utf-8", "replace")[:300]
            finally:
                err.close()
            raise RuntimeError(f"NEAR AI returned HTTP {err.code}: {detail}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"Could not reach NEAR AI: {err.reason}") from err

        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("NEAR AI returned no choices")
        message = choices[0].get("message") or {}

        calls = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            calls.append(
                ToolCall(
                    name=function.get("name", ""),
                    arguments=_loads(function.get("arguments")),
                    id=raw.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                )
            )
        return ModelTurn(content=message.get("content"), tool_calls=calls)


# --- toolbox -----------------------------------------------------------------


class PaymentError(Exception):
    """A payment the app refused or that failed downstream."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


class ToolBox(Protocol):
    """What the agent may touch. `server.py` implements it over its mock state."""

    def get_state(self) -> dict: ...
    def list_bills(self) -> list[dict]: ...
    def recent_activity(self) -> list[dict]: ...
    def pay(self, bill_id: str, amount_ngn: int) -> dict: ...


class PaySigner(Protocol):
    """Signs `pay(meter, amount_ngn)` with a capped function-call key."""

    def sign_pay(self, meter: str, amount_ngn: int) -> dict: ...


@dataclass(frozen=True)
class Limits:
    """The owner's policy, mirrored from the vault's `get_policy()`."""

    monthly_cap_ngn: int
    per_payment_cap_ngn: int
    allowed_meters: frozenset[str]

    def __post_init__(self) -> None:
        if self.per_payment_cap_ngn > self.monthly_cap_ngn:
            raise ValueError("per-payment cap cannot exceed the monthly cap")


# --- agent -------------------------------------------------------------------


@dataclass
class AgentReply:
    reply: str
    token: str | None = None
    receipt_id: str | None = None
    tx_hash: str | None = None
    code: str | None = None
    actions: list[str] = field(default_factory=list)

    def as_voice_payload(self, transcript: str) -> dict:
        """The frozen `/v1/voice` shape. Extra fields are additive."""
        return {
            "transcript": transcript,
            "ignored": False,
            "reply": self.reply,
            "token": self.token,
            "receipt_id": self.receipt_id,
            # Additive (contract rule: additive only).
            "actions": self.actions,
            "tx_hash": self.tx_hash,
        }


class Agent:
    def __init__(
        self,
        *,
        model: Model,
        toolbox: ToolBox,
        limits: Limits,
        signer: PaySigner | None = None,
        max_turns: int = 5,
    ):
        self.model = model
        self.toolbox = toolbox
        self.limits = limits
        self.signer = signer
        self.max_turns = max_turns

    def respond(self, transcript: str) -> AgentReply:
        """Answer one already-gated utterance.

        The wake word check happens in the server, not here — Telegram and the
        wall phone share it there.
        """
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]
        reply = AgentReply(reply="Sorry, I didn't catch that.")
        effect: dict[str, Any] = {}

        for _ in range(self.max_turns):
            turn = self.model.turn(messages, TOOLS)
            messages.append(turn.assistant_message())

            if not turn.tool_calls:
                reply.reply = (turn.content or "").strip() or reply.reply
                return self._apply_effects(reply, effect)

            for call in turn.tool_calls:
                reply.actions.append(call.name)
                result = self._run_tool(call, effect)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result),
                    }
                )

        return self._apply_effects(reply, effect)

    @staticmethod
    def _apply_effects(reply: AgentReply, effect: dict[str, Any]) -> AgentReply:
        reply.token = effect.get("token")
        reply.receipt_id = effect.get("receipt_id")
        reply.tx_hash = effect.get("tx_hash")
        reply.code = effect.get("code")
        return reply

    # --- tool routing --------------------------------------------------------

    def _run_tool(self, call: ToolCall, effect: dict[str, Any]) -> dict:
        try:
            if call.name == "get_state":
                return {"ok": True, "data": self.toolbox.get_state()}
            if call.name == "list_bills":
                return {"ok": True, "data": self.toolbox.list_bills()}
            if call.name == "recent_activity":
                return {"ok": True, "data": self.toolbox.recent_activity()}
            if call.name == "pay_bill":
                return self._pay_bill(call.arguments, effect)
            return {"ok": False, "error": {"code": "unknown_tool",
                                           "message": f"Unknown tool {call.name}",
                                           "detail": {}}}
        except PaymentError as err:
            effect["code"] = err.code
            return {"ok": False,
                    "error": {"code": err.code, "message": err.message,
                              "detail": err.detail}}
        except Exception as err:  # a tool must never take the agent down
            return {"ok": False,
                    "error": {"code": "tool_error", "message": str(err), "detail": {}}}

    def _pay_bill(self, arguments: dict, effect: dict[str, Any]) -> dict:
        """The gate. Nothing is signed or charged unless every rule passes."""
        amount = arguments.get("amount_ngn")
        if not isinstance(amount, int) or isinstance(amount, bool):
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                return {"ok": False,
                        "error": {"code": "bad_amount",
                                  "message": policy_rules.MESSAGES["bad_amount"],
                                  "detail": {}}}

        bills = self.toolbox.list_bills()
        bill = None
        bill_id = arguments.get("bill_id") or ""
        if bill_id:
            bill = next((b for b in bills if b.get("id") == bill_id), None)
        if bill is None:
            bill = next((b for b in bills if b.get("kind") == "electricity"), None)
        if bill is None:
            return {"ok": False,
                    "error": {"code": "unknown_bill",
                              "message": "I don't have that bill saved.",
                              "detail": {"bill_id": bill_id}}}

        # A plan is sold at its own price. Refuse a mispriced attempt before it can
        # reach the vendor, so the user hears the real number.
        plan_price = bill.get("plan_price_ngn")
        if isinstance(plan_price, int) and amount != plan_price:
            effect["code"] = "plan_price_mismatch"
            return {
                "ok": False,
                "error": {
                    "code": "plan_price_mismatch",
                    "message": (
                        f"{bill.get('label', 'That bill')} costs ₦{plan_price:,}. "
                        "Nothing was charged."
                    ),
                    "detail": {"amount_ngn": amount, "plan_price_ngn": plan_price},
                },
            }

        state = self.toolbox.get_state()
        meter = str(bill.get("reference") or "")
        rejection = policy_rules.check_payment(
            monthly_cap_ngn=self.limits.monthly_cap_ngn,
            per_payment_cap_ngn=self.limits.per_payment_cap_ngn,
            spent_this_period_ngn=int(state.get("spent_ngn") or 0),
            balance_ngn=int(state.get("balance_ngn") or 0),
            amount_ngn=amount,
            meter_allowed=meter in self.limits.allowed_meters,
        )
        if rejection is not None:
            effect["code"] = rejection.code
            return {"ok": False, "error": rejection.as_dict()}

        # Authorise first, then buy. A signed transaction that is never broadcast
        # costs nothing, but a purchase with no authorisation is a real problem.
        # Fail closed: if the key cannot sign, nothing is charged.
        if self.signer is not None:
            try:
                signed = self.signer.sign_pay(meter=meter, amount_ngn=amount)
            except Exception:
                effect["code"] = "authorisation_failed"
                return {
                    "ok": False,
                    "error": {
                        "code": "authorisation_failed",
                        "message": (
                            "I couldn't authorise that payment just now. "
                            "Nothing was charged."
                        ),
                        "detail": {},
                    },
                }
            effect["tx_hash"] = signed.get("tx_hash")

        receipt = self.toolbox.pay(bill["id"], amount)
        effect["token"] = receipt.get("token")
        effect["receipt_id"] = receipt.get("id")
        return {"ok": True, "data": receipt}


def build_agent(toolbox: ToolBox, limits: Limits, signer: PaySigner | None = None) -> Agent:
    """Real model when a key is configured, deterministic model otherwise.

    The server calls this, so the key stays a config value and a checkout with no
    key still runs — the same way `vtpass.py` is dry-run by default.
    """
    if os.environ.get("NEAR_AI_API_KEY"):
        return Agent(model=NearAiModel(), toolbox=toolbox, limits=limits, signer=signer)
    return Agent(model=FakeModel(), toolbox=toolbox, limits=limits, signer=signer)
