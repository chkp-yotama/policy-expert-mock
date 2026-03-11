"""
Prompt-router scenario — routes based on keywords matching real policy-expert agent skills.

Real ask_user flows (from rule-placement skill):
  - Place/add rule with >1 matching reference rules → user picks one
  - Ambiguous rulebase type (access/NAT/threat/HTTPS) → user clarifies
  - Multiple packages found → user picks one

Everything else is read-only → simple streaming response.
"""

import asyncio
import re
from collections.abc import AsyncGenerator

from config import settings
from scenarios.base import AbstractScenario

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NEGATIVE_DECISIONS = {"cancel", "no", "none", "skip", "reject", "Reject"}


def _match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


# ---------------------------------------------------------------------------
# Route table
# ---------------------------------------------------------------------------

_ROUTES: list[dict] = [

    # ── Delete rule: accept / reject ─────────────────────────────────────────
    {
        "patterns": [r"\bdelete.*(rule|policy)\b", r"\bremove.*(rule|policy)\b"],
        "kind": "ask_user",
        "status": "Preparing deletion...",
        "reasoning": "The user wants to delete a rule. I'll look it up first, then ask for confirmation.",
        "tool_calls": [
            {
                "tool_name": "show_access_rule",
                "tool_call_id": "tc-del-001",
                "args": {"name": "Network", "rule-number": 1},
                "response": '{"rule-number":1,"name":"Cleanup Rule","src":"Any","dst":"Any","service":"Any","action":"Accept","enabled":true}',
            },
        ],
        "question": "Are you sure you want to delete rule#1? This action cannot be undone.",
        "operation": "delete_rule",
        "options": ["Accept", "Reject"],
        "approved_fn": lambda _: "Rule deleted successfully.",
        "rejected": "Deletion cancelled. Rule#1 remains unchanged.",
    },

    # ── Continue: single-option acknowledgement ───────────────────────────────
    {
        "patterns": [r"\bshow continue\b", r"\bcontinue\b"],
        "kind": "ask_user",
        "status": "Checking tool call budget...",
        "question": "We reached the maximum number of tool calls for this step. Do you want to continue?",
        "operation": "continue_execution",
        "options": ["Continue"],
        "approved_fn": lambda _: (
            "Continuing analysis...\n\n"
            "Found 3 additional rules matching your query:\n"
            "rule#14 — InternalHosts → Internet → HTTP → Accept\n"
            "rule#15 — InternalHosts → Internet → FTP → Drop\n"
            "rule#16 — Any → Any → Any → Drop (final cleanup)"
        ),
        "rejected": "Execution stopped.",
    },

    # ── Rule placement: place/add a rule (ask_user: select reference rule) ──
    {
        "patterns": [r"\bplace rule\b", r"\badd rule\b", r"\bnew rule\b",
                     r"\brule placement\b", r"\bwhere.*(put|add|place).*rule\b",
                     r"\boptimal position\b"],
        "kind": "ask_user",
        "status": "Searching for reference rules...",
        "reasoning": "I need to find reference rules to determine optimal placement. I'll call inquire_rules.",
        "tool_calls": [
            {
                "tool_name": "inquire_rules",
                "tool_call_id": "tc-place-001",
                "args": {"package": "Standard", "layer": "Network", "rule_name": ""},
                "response": '{"status":"RULES_INQUIRED","rules":[{"uid":"uid-42","rule-number":42,"name":"Allow HTTPS"},{"uid":"uid-57","rule-number":57,"name":"Allow DNS"},{"uid":"uid-89","rule-number":89,"name":"Drop DMZ"}]}',
            },
        ],
        "question": (
            "I found 3 rules matching your criteria. "
            "Please select the reference rule to use for placement:\n\n"
            "1. rule#42 — Allow HTTPS from WebServers to Internet (Network layer)\n"
            "2. rule#57 — Allow DNS from InternalHosts to DNS-Servers (Network layer)\n"
            "3. rule#89 — Drop all from Untrusted to DMZ (Network layer)"
        ),
        "operation": "select_reference_rule",
        "options": ["rule#42", "rule#57", "rule#89"],
        "approved_fn": lambda decision: (
            f"Placement recommendation: insert your new rule **before {decision}** "
            f"(position {decision.replace('rule#', '')}).\n\n"
            "This placement ensures the new rule is evaluated before broader drop rules "
            "and after existing allow rules for the same traffic scope."
        ),
        "rejected": "Placement cancelled. No changes were made.",
    },

    # ── Rule placement: policy fetch in progress ─────────────────────────────
    {
        "patterns": [r"\bfetch policy\b", r"\brefresh policy\b", r"\bpolicy fetch\b"],
        "kind": "simple",
        "status": "Checking policy fetch status...",
        "answer": (
            "Policy fetch is currently in progress for package 'Standard'. "
            "This may take a few minutes. Please retry your request shortly."
        ),
    },

    # ── Firewall policy: ambiguous type → ask user ────────────────────────────
    {
        "patterns": [r"\bshow (me |the |all )?rules\b", r"\blist rules\b",
                     r"\bview (the |my )?policy\b", r"\bshow policy\b",
                     r"\bwhat rules\b"],
        "kind": "ask_user",
        "status": "Resolving policy type...",
        "question": (
            "Which rulebase type would you like to query? "
            "The 'Standard' package contains multiple rulebases."
        ),
        "operation": "select_rulebase_type",
        "options": ["Access rules", "NAT rules", "Threat prevention", "HTTPS inspection"],
        "approved_fn": lambda decision: {
            "Access rules": (
                "Found 5 access rules in layer 'Network':\n\n"
                "rule#1  — Any → Any → Any → Accept (Cleanup rule)\n"
                "rule#12 — WebServers → Internet → HTTPS → Accept\n"
                "rule#23 — InternalHosts → DNS-Servers → DNS → Accept\n"
                "rule#42 — DMZ → InternalHosts → Any → Drop\n"
                "rule#57 — Any → Any → Any → Drop (Final drop)"
            ),
            "NAT rules": (
                "Found 3 NAT rules in package 'Standard':\n\n"
                "nat#1 — Hide NAT: InternalNetwork (10.0.0.0/8) → Gateway external IP\n"
                "nat#2 — Static NAT: WebServer-Internal (10.1.1.10) ↔ WebServer-Public (203.0.113.10)\n"
                "nat#3 — Hide NAT: DMZ-Network (172.16.0.0/16) → Gateway external IP"
            ),
            "Threat prevention": (
                "Found 2 threat prevention rules in layer 'Threat Prevention':\n\n"
                "rule#1 — Any → Any → Optimized profile (prevent high confidence, detect medium)\n"
                "rule#2 — InternalHosts → Any → Strict profile (prevent all)"
            ),
            "HTTPS inspection": (
                "Found 3 HTTPS inspection rules:\n\n"
                "rule#1 — Bypass: Any → TrustedCertAuthorities → No inspection\n"
                "rule#2 — Inspect: InternalHosts → Social-Networks → Full inspection\n"
                "rule#3 — Bypass: Any → FinancialSites → No inspection"
            ),
        }.get(decision,
              f"Querying '{decision}' rulebase... No results found. "
              "Please verify the layer name or try a different filter."),
        "rejected": "Query cancelled.",
    },

    # ── Firewall policy: specific access rule queries (simple) ───────────────
    {
        "patterns": [r"\baccess rules?\b", r"\baccess rulebase\b",
                     r"\bfirewall rules?\b", r"\bshow access\b", r"\bsrc:\b", r"\bdst:\b",
                     r"\bzero.hit\b", r"\bunused rule\b"],
        "kind": "simple",
        "status": "Querying access rulebase...",
        "reasoning": "I need to query the access rulebase. I'll use show_access_rulebase with the Network layer.",
        "tool_calls": [
            {
                "tool_name": "show_access_rulebase",
                "tool_call_id": "tc-001",
                "args": {"name": "Network", "limit": 50},
                "response": '[{"rule-number":12,"src":"WebServers","dst":"Internet","service":"https","action":"Accept"},{"rule-number":34,"src":"WebServers","dst":"Internet","service":"http","action":"Accept"}]',
            },
        ],
        "answer": (
            "Found 2 rules matching your query:\n\n"
            "rule#12 — WebServers → Internet → HTTPS (tcp/443) → Accept | logged\n"
            "rule#34 — WebServers → Internet → HTTP (tcp/80) → Accept | logged\n\n"
            "Both rules are installed on Policy Targets (all gateways)."
        ),
    },

    # ── NAT ───────────────────────────────────────────────────────────────────
    {
        "patterns": [r"\bnat\b", r"\bnetwork address\b", r"\bhide nat\b", r"\bstatic nat\b"],
        "kind": "simple",
        "status": "Querying NAT rulebase...",
        "reasoning": "I need to query NAT rules. I'll use show_nat_rulebase for the Standard package.",
        "tool_calls": [
            {
                "tool_name": "show_nat_rulebase",
                "tool_call_id": "tc-002",
                "args": {"package": "Standard"},
                "response": '[{"rule-number":2,"original-source":"WebServer-Internal","translated-source":"WebServer-Public","method":"static"}]',
            },
        ],
        "answer": (
            "Found 1 NAT rule matching your query:\n\n"
            "nat#2 — Static NAT\n"
            "  Original: WebServer-Internal (10.1.1.10) → Any\n"
            "  Translated: WebServer-Public (203.0.113.10) → Original\n"
            "  Method: static | Install on: GW-01"
        ),
    },

    # ── Threat prevention / CVE ───────────────────────────────────────────────
    {
        "patterns": [r"\bcve\b", r"\bCVE-\d", r"\bthreat\b", r"\bips\b",
                     r"\bprotection\b", r"\bmalware\b", r"\bintrusion\b",
                     r"\bthreat prevention\b"],
        "kind": "simple",
        "status": "Querying threat prevention...",
        "reasoning": "I'll check CVE protection status using check_cve_protection, then verify IPS blade status per gateway.",
        "tool_calls": [
            {
                "tool_name": "check_cve_protection",
                "tool_call_id": "tc-003",
                "args": {"cve": "CVE-2021-44228"},
                "response": '{"protection":"Apache Log4j RCE","confidence-level":"High","severity":"Critical","gateways":[{"name":"GW-01","ips-blade":true,"profile":"Strict"},{"name":"GW-02","ips-blade":true,"profile":"Optimized"}]}',
            },
        ],
        "answer": (
            "CVE protection check result:\n\n"
            "Protection found: 'Apache Log4j RCE (CVE-2021-44228)'\n"
            "  Confidence level: High\n"
            "  Severity: Critical\n\n"
            "Gateway GW-01:\n"
            "  IPS blade: enabled ✓\n"
            "  Active profile: Strict — prevents High confidence threats ✓\n"
            "  Status: PROTECTED\n\n"
            "Gateway GW-02:\n"
            "  IPS blade: enabled ✓\n"
            "  Active profile: Optimized — detects but does not prevent Medium confidence\n"
            "  Status: PROTECTED (High confidence is prevented by Optimized profile)"
        ),
    },

    # ── HTTPS / SSL inspection ────────────────────────────────────────────────
    {
        "patterns": [r"\bhttps inspection\b", r"\bssl inspection\b",
                     r"\bbypass\b", r"\btls inspection\b"],
        "kind": "simple",
        "status": "Querying HTTPS inspection policy...",
        "reasoning": "I'll query the HTTPS inspection rulebase to find bypass and inspect rules.",
        "tool_calls": [
            {
                "tool_name": "show_https_rulebase",
                "tool_call_id": "tc-004",
                "args": {"name": "HTTPS Inspection"},
                "response": '[{"rule-number":1,"action":"Bypass","dst":"TrustedCertAuthorities"},{"rule-number":2,"action":"Inspect","src":"InternalHosts","dst":"Social-Networks"},{"rule-number":3,"action":"Bypass","dst":"FinancialSites"}]',
            },
        ],
        "answer": (
            "HTTPS inspection policy — 3 rules:\n\n"
            "rule#1 — Bypass | Any → TrustedCertAuthorities | reason: trusted CA\n"
            "rule#2 — Inspect | InternalHosts → Social-Networks | full inspection\n"
            "rule#3 — Bypass | Any → FinancialSites | reason: privacy / compliance\n\n"
            "Traffic not matched by any rule defaults to: Bypass."
        ),
    },

    # ── Object lookup ─────────────────────────────────────────────────────────
    {
        "patterns": [r"\bfind object\b", r"\bshow object\b", r"\blookup\b",
                     r"\bwhat is\b", r"\bresolve\b", r"\bobject uid\b",
                     r"\bwho is\b"],
        "kind": "simple",
        "status": "Looking up object...",
        "reasoning": "I'll search for the object by name using show_objects.",
        "tool_calls": [
            {
                "tool_name": "show_objects",
                "tool_call_id": "tc-005",
                "args": {"name": "WebServers", "details-level": "full"},
                "response": '{"name":"WebServers","type":"host-group","uid":"a3f2c1d0-4b5e-4f6a-8c9d-1e2f3a4b5c6d","members":["WebServer-01","WebServer-02","WebServer-03"]}',
            },
        ],
        "answer": (
            "Object found:\n\n"
            "Name: WebServers\n"
            "Type: host-group\n"
            "UID: a3f2c1d0-4b5e-4f6a-8c9d-1e2f3a4b5c6d\n"
            "Members: WebServer-01 (10.1.1.10), WebServer-02 (10.1.1.11), WebServer-03 (10.1.1.12)\n"
            "Used in: rule#12, rule#34, nat#2"
        ),
    },

    # ── Infrastructure / gateways ─────────────────────────────────────────────
    {
        "patterns": [r"\bgateway\b", r"\bcluster\b", r"\binstalled policy\b",
                     r"\bblade\b", r"\binfrastructure\b", r"\bgw\b"],
        "kind": "simple",
        "status": "Querying infrastructure...",
        "reasoning": "I'll query all gateways with full details to get blade status and installed policies.",
        "tool_calls": [
            {
                "tool_name": "show_gateways_and_servers",
                "tool_call_id": "tc-006",
                "args": {"details-level": "full"},
                "response": '[{"name":"GW-01","ip":"192.168.1.1","type":"simple-gateway","policy":{"name":"Standard"},"blades":{"firewall":true,"ips":true,"application-control":true,"url-filtering":true}},{"name":"GW-02","ip":"192.168.1.2","type":"simple-gateway","policy":{"name":"Standard"},"blades":{"firewall":true,"ips":true,"application-control":false}}]',
            },
        ],
        "answer": (
            "Gateways found:\n\n"
            "GW-01 (192.168.1.1) — standalone | status: connected\n"
            "  Installed policy: Standard (last install: 2 hours ago)\n"
            "  Blades: Firewall ✓ | IPS ✓ | Application Control ✓ | URL Filtering ✓\n\n"
            "GW-02 (192.168.1.2) — standalone | status: connected\n"
            "  Installed policy: Standard (last install: 2 hours ago)\n"
            "  Blades: Firewall ✓ | IPS ✓ | Application Control ✗"
        ),
    },

    # ── General / out of scope ────────────────────────────────────────────────
    {
        "patterns": [r"\bhelp\b", r"\bwhat can\b", r"\bskills\b", r"\bcommands\b"],
        "kind": "simple",
        "status": "Loading capabilities...",
        "answer": (
            "I can help you with:\n\n"
            "• **Firewall policy** — query access rules, NAT rules, find zero-hit rules\n"
            "• **Rule placement** — find optimal position for new firewall rules\n"
            "• **Threat prevention** — check CVE coverage, IPS status, threat profiles\n"
            "• **HTTPS inspection** — query SSL/TLS inspection and bypass rules\n"
            "• **Object lookup** — resolve hosts, networks, groups, services by name or UID\n"
            "• **Infrastructure** — query gateways, installed policies, blade status\n\n"
            "Try: 'show access rules', 'check CVE-2021-44228', 'place rule in Standard package', "
            "'find object WebServers', 'list gateways'"
        ),
    },
]

_FALLBACK_ANSWER = (
    "I'm not sure how to help with that. "
    "This question doesn't clearly match any of my available skills: "
    "firewall-policy, rule-placement, threat-prevention, https-inspection, "
    "object-lookup, or infrastructure. "
    "Could you rephrase or provide more context?"
)


# ---------------------------------------------------------------------------

class PromptRouterScenario(AbstractScenario):
    """Routes to different flows based on keywords in the user's question."""

    _route_cache: dict[str, dict] = {}

    async def generate_chunks(
        self,
        run_id: str,
        question: str,
        history: list[dict],
        turn: int,
    ) -> AsyncGenerator[str, None]:
        question_id = f"{run_id}-q{turn}"

        if turn == 0:
            route = self._find_route(question)
            if route:
                self._route_cache[run_id] = route
        else:
            route = self._route_cache.get(run_id)

        # ── ask_user ─────────────────────────────────────────────────────────
        if route and route["kind"] == "ask_user":
            if turn == 0:
                yield self._status_chunk(run_id, question_id, route["status"])
                await self._delay()

                reasoning = route.get("reasoning")
                if reasoning:
                    async for chunk in self._stream_reasoning(run_id, question_id, reasoning):
                        yield chunk

                for tc in route.get("tool_calls", []):
                    call_id = tc["tool_call_id"]
                    yield self._tool_call_chunk(run_id, question_id, tc["tool_name"], call_id, tc["args"])
                    await self._delay()
                    yield self._tool_response_chunk(run_id, question_id, tc["tool_name"], call_id, tc["response"])
                    await self._delay()

                await asyncio.sleep(settings.ask_user_delay)
                yield self._ask_user_chunk(
                    run_id=run_id,
                    question_id=question_id,
                    question_text=route["question"],
                    operation_name=route["operation"],
                    options=route["options"],
                )
            else:
                decision = self._last_user_message(history)
                if decision in _NEGATIVE_DECISIONS:
                    answer = route["rejected"]
                elif "approved_fn" in route:
                    answer = route["approved_fn"](decision)
                else:
                    answer = route.get("approved", "Done.")

                yield self._status_chunk(run_id, question_id, "Processing your selection...")
                await self._delay()
                async for chunk in self._stream_text(run_id, question_id, answer):
                    yield chunk
                yield self._final_response(run_id, question_id, answer)

        # ── simple ───────────────────────────────────────────────────────────
        elif route and route["kind"] == "simple":
            yield self._status_chunk(run_id, question_id, route["status"])
            await self._delay()

            # Emit reasoning + tool calls if defined on the route
            reasoning = route.get("reasoning")
            if reasoning:
                async for chunk in self._stream_reasoning(run_id, question_id, reasoning):
                    yield chunk

            for tc in route.get("tool_calls", []):
                call_id = tc["tool_call_id"]
                yield self._tool_call_chunk(run_id, question_id, tc["tool_name"], call_id, tc["args"])
                await self._delay()
                yield self._tool_response_chunk(run_id, question_id, tc["tool_name"], call_id, tc["response"])
                await self._delay()

            async for chunk in self._stream_text(run_id, question_id, route["answer"]):
                yield chunk
            yield self._final_response(run_id, question_id, route["answer"])

        # ── fallback ─────────────────────────────────────────────────────────
        else:
            yield self._status_chunk(run_id, question_id, "Analyzing request...")
            await self._delay()
            async for chunk in self._stream_text(run_id, question_id, _FALLBACK_ANSWER):
                yield chunk
            yield self._final_response(run_id, question_id, _FALLBACK_ANSWER)

    @staticmethod
    def _find_route(question: str) -> dict | None:
        for route in _ROUTES:
            if _match(route["patterns"], question):
                return route
        return None

    @staticmethod
    def _last_user_message(history: list[dict]) -> str:
        for entry in reversed(history):
            if entry.get("role") == "user":
                return entry.get("content", "").strip()
        return ""
