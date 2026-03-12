# Test Prompts Reference

Default scenario: `prompt_router` (keyword-based routing).
Switch scenario via `POST /admin/scenario` with `{"name": "<scenario>"}`.

---

## Scenarios

Available scenario names: `prompt_router`, `ask_user_single`, `ask_user_chained`, `simple_response`, `error`

---

## `prompt_router` — Prompt Routing by Keyword

### ask_user flows (multi-turn, prompts for a decision)

#### Delete rule
Triggers: `delete rule`, `remove rule`, `delete policy`, `remove policy`

Flow:
1. Shows tool call (`show_access_rule`) + reasoning
2. Asks: *"Are you sure you want to delete rule#1?"*
   - Options: `Accept` / `Reject`
3. `Accept` → "Rule deleted successfully."
4. `Reject` → "Deletion cancelled."

---

#### Continue execution
Triggers: `continue`, `show continue`

Flow:
1. Asks: *"We reached the maximum number of tool calls. Do you want to continue?"*
   - Options: `Continue`
2. `Continue` → lists 3 additional rules found

---

#### Place / add rule
Triggers: `place rule`, `add rule`, `new rule`, `rule placement`, `where to put rule`, `where to add rule`, `where to place rule`, `optimal position`

Flow:
1. Shows tool call (`inquire_rules`) + reasoning
2. Asks: *"Please select the reference rule for placement"*
   - Options: `rule#42` / `rule#57` / `rule#89`
3. Any option → placement recommendation relative to selected rule
4. `Reject` / negative → "Placement cancelled."

---

#### Show rules (ambiguous rulebase type)
Triggers: `show rules`, `show all rules`, `show the rules`, `list rules`, `view policy`, `view the policy`, `view my policy`, `show policy`, `what rules`

Flow:
1. Asks: *"Which rulebase type would you like to query?"*
   - Options: `Access rules` / `NAT rules` / `Threat prevention` / `HTTPS inspection`
2. Each option returns the matching rulebase content

---

### Simple flows (single-turn, streaming response)

| Trigger prompts | Response |
|---|---|
| `access rules`, `firewall rules`, `show access`, `access rulebase`, `zero-hit`, `unused rule`, `src:`, `dst:` | 2 access rules (WebServers → Internet) |
| `nat`, `network address`, `hide nat`, `static nat` | 1 static NAT rule |
| `threat`, `cve`, `CVE-2021-44228`, `ips`, `protection`, `malware`, `intrusion`, `threat prevention` | CVE protection check result for Log4j |
| `https inspection`, `ssl inspection`, `tls inspection`, `bypass` | HTTPS inspection policy (3 rules) |
| `find object`, `show object`, `lookup`, `what is`, `resolve`, `object uid`, `who is` | Object details for `WebServers` group |
| `gateway`, `cluster`, `blade`, `gw`, `installed policy`, `infrastructure` | 2 gateways (GW-01, GW-02) with blade status |
| `help`, `what can`, `skills`, `commands` | Capabilities overview |
| *(anything else)* | Fallback: "I'm not sure how to help with that." |

---

### Note on route priority
Routes are evaluated **top to bottom**. First match wins. Example: `"delete access rules"` → matches **delete rule** (not access rules) because delete-rule pattern comes first.

---

## `ask_user_single` — Single Confirmation

Any prompt triggers this scenario (content ignored).

Flow:
1. Asks: *"Do you want to apply the proposed policy change? This will affect all network traffic on port 443."*
   - Options: `approve` / `reject`
2. `approve` → "Policy change applied successfully."
3. anything else → "Policy change was cancelled."

---

## `ask_user_chained` — Two Confirmations

Any prompt triggers this scenario (content ignored).

Flow:
1. Asks: *"I'm about to modify the firewall policy to block port 443 outbound. Do you want to proceed?"*
   - Options: `approve` / `reject`
2. Asks: *"This will affect all 47 endpoints in your production scope. This change is irreversible without a manual rollback. Are you sure?"*
   - Options: `confirm` / `cancel`
3. Both approved → "Firewall policy updated. Port 443 outbound traffic is now blocked..."
4. Any negative → "Operation cancelled."

Negative decisions: `reject`, `cancel`, `no`

---

## `simple_response`

Any prompt → single streaming text response (no ask_user).

---

## `error`

Any prompt → returns an error response.

---

## Admin API

```
POST /admin/scenario        {"name": "ask_user_single"}   # switch scenario
POST /admin/reset                                          # reset all state
GET  /admin/status                                        # current scenario + available
DELETE /admin/conversation/{run_id}                       # reset specific run
```
