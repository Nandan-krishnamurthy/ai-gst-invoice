# GST MCP Invoice - System Document

## 1. System Overview

This system is a hybrid conversational and form-driven invoice platform with three coordinated runtime tracks:

1. Interpreter track: upload image or text, extract customer and invoice signals, and suggest actions.
2. Customer track: collect or confirm customer details and persist customer + contact.
3. Invoice track: maintain a session-bound draft invoice, update details conversationally, then finalize or create directly.

Primary backend composition:

1. API bootstrap and router registration in [main.py](main.py).
2. Agent routes in [app/agent/router.py](app/agent/router.py).
3. Interpreter routes in [app/agent/interpreter/handler.py](app/agent/interpreter/handler.py).
4. Customer routes in [app/customer/router.py](app/customer/router.py).
5. Direct invoice routes in [invoice/router.py](invoice/router.py).

Primary frontend composition:

1. Stateful orchestration in [frontend/src/App.jsx](frontend/src/App.jsx).
2. Interpreter visual preview in [frontend/src/InterpreterPreview.jsx](frontend/src/InterpreterPreview.jsx).
3. Invoice visual and editable preview in [frontend/src/InvoicePreview.jsx](frontend/src/InvoicePreview.jsx).

---

## 2. Architecture Flow (input -> backend -> frontend -> DB)

This section documents both directions because runtime behavior is request/response, not one-way.

### 2.1 Runtime Loop A: User input to UI state

1. Input originates in frontend:
2. Text command from command bar in [frontend/src/App.jsx](frontend/src/App.jsx#L776).
3. Image upload from command bar in [frontend/src/App.jsx](frontend/src/App.jsx#L760).

1. Backend processing:
2. Invoice draft messages go to [app/agent/router.py](app/agent/router.py#L30) from [frontend/src/App.jsx](frontend/src/App.jsx#L560).
3. Interpreter uploads go to [app/agent/interpreter/handler.py](app/agent/interpreter/handler.py#L22) from [frontend/src/App.jsx](frontend/src/App.jsx#L458).
4. Customer create direct calls go to [app/customer/router.py](app/customer/router.py#L52) from [frontend/src/App.jsx](frontend/src/App.jsx#L380).
5. Direct invoice create calls go to [invoice/router.py](invoice/router.py#L37) from [frontend/src/App.jsx](frontend/src/App.jsx#L656).

1. Frontend response handling:
2. Agent responses are normalized in [frontend/src/App.jsx](frontend/src/App.jsx#L234).
3. Step switching via currentStep and render guards in [frontend/src/App.jsx](frontend/src/App.jsx#L223).

### 2.2 Runtime Loop B: Persistence path

1. DB persistence points:
2. Invoice draft create and update in [app/agent/draft_service.py](app/agent/draft_service.py#L72) and [app/agent/draft_service.py](app/agent/draft_service.py#L163).
3. Agent session and active_draft_id writes in [app/agent/session_service.py](app/agent/session_service.py).
4. Final invoice row create in [app/db/crud.py](app/db/crud.py#L4).
5. Customer row create in [app/customer/crud.py](app/customer/crud.py#L46).
6. Customer contact row create in [app/customer/handler.py](app/customer/handler.py#L310).

### 2.3 Database models used by the flow

1. AgentSession with active_draft_id in [app/db/models.py](app/db/models.py#L14).
2. Invoice with JSONB seller, buyer, items and status enum in [app/db/models.py](app/db/models.py#L23).

---

## 3. Customer Flow (step-by-step)

Customer flow exists in two variants: conversational through agent endpoint and direct API create.

### 3.1 Conversational customer flow (through /agent/invoice/draft)

1. Trigger:
2. Message matches explicit customer intent via [app/customer/intent.py](app/customer/intent.py#L13), or session already has active customer conversation via [app/customer/handler.py](app/customer/handler.py#L86).
3. Agent router diverts to customer handler in [app/agent/router.py](app/agent/router.py#L41).

1. State bootstrap:
2. Session-scoped in-memory state created by _get_state in [app/customer/handler.py](app/customer/handler.py#L60).
3. customer_state shape includes name, gstin, phone, email, city, state.
4. awaiting field controls next expected input.

1. Initial extraction stage:
2. Inline parser and fallback LLM extraction run in [app/customer/handler.py](app/customer/handler.py#L328).
3. If name cannot be parsed, returns COLLECTING_INFO and prompt.

1. Optional field collection stage:
2. Ordered progression controlled by _advance_customer_flow in [app/customer/handler.py](app/customer/handler.py#L251).
3. Awaited field-specific parsing and skip/confirm handling in [app/customer/handler.py](app/customer/handler.py#L374).
4. Confirm intent is evaluated after field extraction, preserving latest value before save.

1. Confirmation stage:
2. awaiting == confirm branch in [app/customer/handler.py](app/customer/handler.py#L495).
3. Confirm keywords call _save_customer.
4. Cancel clears customer session state and exits flow.

1. Persistence stage:
2. _save_customer performs duplicate check then create_customer in [app/customer/handler.py](app/customer/handler.py#L270).
3. Contact row inserted in same transaction via CustomerContact in [app/customer/handler.py](app/customer/handler.py#L310).
4. State is cleared after success.

### 3.2 Direct customer create flow (/customer/create)

1. Triggered by frontend Confirm Customer button in [frontend/src/App.jsx](frontend/src/App.jsx#L811).
2. Request sent in [frontend/src/App.jsx](frontend/src/App.jsx#L380).
3. Endpoint in [app/customer/router.py](app/customer/router.py#L52) calls _save_customer and then re-fetches persisted row.

### 3.3 Frontend customer flow behavior

1. Enter customer step from interpreter action in [frontend/src/App.jsx](frontend/src/App.jsx#L333).
2. currentStep changes to customer in [frontend/src/App.jsx](frontend/src/App.jsx#L345).
3. Customer preview panel renders when isCustomerFlow in [frontend/src/App.jsx](frontend/src/App.jsx#L803).
4. Confirm Customer button only appears when agentState == awaiting_confirmation in [frontend/src/App.jsx](frontend/src/App.jsx#L811).
5. On create success, currentStep moves to invoice in [frontend/src/App.jsx](frontend/src/App.jsx#L425).

---

## 4. Invoice Flow (step-by-step)

Invoice flow has two main tracks: agent-draft track and direct create track.

### 4.1 Agent draft track

1. Trigger:
2. Text input submission in non-customer mode from [frontend/src/App.jsx](frontend/src/App.jsx#L493).
3. POST /agent/invoice/draft route in [app/agent/router.py](app/agent/router.py#L30).

1. Draft availability guarantee:
2. handle_message in [app/agent/agent_service.py](app/agent/agent_service.py#L36) ensures a session exists and ensures active draft exists.
3. If none exists, create_draft is called and bound to active_draft_id.

1. Supported update branches in handle_message:
2. confirm/accept/yes branch transitions to draft_created.
3. create invoice extraction branch.
4. seller or buyer update branch.
5. standalone GSTIN update branch.
6. GST rate update branch.
7. HSN update branch.
8. standalone address update branch.
9. add item branch.
10. finalize branch.
11. LLM fallback branch.

1. Draft mutation implementation:
2. Every structural update uses update_draft in [app/agent/draft_service.py](app/agent/draft_service.py#L163).
3. GST summary and totals are recalculated each update.

1. Confirm stage:
2. Frontend confirm button sends message confirm in [frontend/src/App.jsx](frontend/src/App.jsx#L582).
3. Backend confirm branch checks critical validation and returns DRAFT_CREATED or keeps AWAITING_CONFIRMATION.

1. Finalize stage (agent route):
2. Frontend agent finalize path calls /agent/invoice/finalize in [frontend/src/App.jsx](frontend/src/App.jsx#L698).
3. Router finalize endpoint in [app/agent/router.py](app/agent/router.py#L140) requires confirm true, finalizes draft, commits, writes PDF, clears active_draft_id.

### 4.2 Direct create track (/invoice/create)

1. Triggered by invoice-step finalize in frontend currentStep == invoice path in [frontend/src/App.jsx](frontend/src/App.jsx#L617).
2. Sends normalized payload to /invoice/create in [frontend/src/App.jsx](frontend/src/App.jsx#L656).
3. Endpoint in [invoice/router.py](invoice/router.py#L37) builds InvoiceRequest, computes invoice via engine, persists via CRUD create_invoice.
4. Returns InvoiceResponse contract from [invoice/model.py](invoice/model.py#L32).

### 4.3 Interpreter-assisted pre-invoice track

1. Upload handled by run_interpreter endpoint in [app/agent/interpreter/handler.py](app/agent/interpreter/handler.py#L22).
2. Parsing + intent actions assembled by interpret_conversation in [app/agent/interpreter/service.py](app/agent/interpreter/service.py#L30).
3. Frontend receives interpreterResult and can branch to add customer or create invoice actions.

---

## 5. State Management (agentState, currentStep)

### 5.1 agentState

Backend source-of-truth enum is [app/agent/agent_state.py](app/agent/agent_state.py#L4):

1. collecting_info
2. need_more_info
3. draft_created
4. awaiting_confirmation
5. finalized
6. error

Frontend local state:

1. Defined in [frontend/src/App.jsx](frontend/src/App.jsx#L207).
2. Set from backend response in applyAgentPayload [frontend/src/App.jsx](frontend/src/App.jsx#L234).
3. Also manually set in customer input parsing branch in [frontend/src/App.jsx](frontend/src/App.jsx#L495).

Behavior impact:

1. draft_created shows finalize prompt branch [frontend/src/App.jsx](frontend/src/App.jsx#L794).
2. awaiting_confirmation controls visibility of Confirm Customer and Confirm Invoice buttons [frontend/src/App.jsx](frontend/src/App.jsx#L811).

### 5.2 currentStep

Frontend-only UI mode switch defined in [frontend/src/App.jsx](frontend/src/App.jsx#L223):

1. interpreter
2. customer
3. invoice

Transitions:

1. interpreter -> customer via handleAddCustomerStep [frontend/src/App.jsx](frontend/src/App.jsx#L333).
2. customer -> invoice after customer creation [frontend/src/App.jsx](frontend/src/App.jsx#L425).
3. interpreter -> invoice via handleCreateInvoiceStep [frontend/src/App.jsx](frontend/src/App.jsx#L434).
4. resets to interpreter in resetSessionFlow [frontend/src/App.jsx](frontend/src/App.jsx#L282).

---

## 6. Frontend Rendering Rules (Very Important)

This section is the practical render contract in [frontend/src/App.jsx](frontend/src/App.jsx).

### 6.1 Top-level render gates

1. Agent text line renders when agentState != draft_created at [frontend/src/App.jsx](frontend/src/App.jsx#L793).
2. Draft-created block renders only when agentState == draft_created at [frontend/src/App.jsx](frontend/src/App.jsx#L794).
3. InvoicePreview from agent payload renders only when:
4. not in customer flow, and
5. invoicePreview exists, and
6. invoicePreview.type is not customer_preview or customer_created.
7. Gate implemented in hasInvoicePreview [frontend/src/App.jsx](frontend/src/App.jsx#L745) and render at [frontend/src/App.jsx](frontend/src/App.jsx#L800).

### 6.2 Customer rendering rules

1. CustomerPreview component renders only if currentStep == customer and customerDraft exists at [frontend/src/App.jsx](frontend/src/App.jsx#L803).
2. Confirm Customer button renders only if currentStep == customer and agentState == awaiting_confirmation at [frontend/src/App.jsx](frontend/src/App.jsx#L811).
3. Customer success message renders from customerSuccess state at [frontend/src/App.jsx](frontend/src/App.jsx#L825).

### 6.3 Invoice confirmation and finalize rendering rules

1. Confirm Invoice button renders only if:
2. currentStep != customer,
3. agentState == awaiting_confirmation,
4. hasInvoicePreview == true.
5. Gate at [frontend/src/App.jsx](frontend/src/App.jsx#L821).

1. Editable invoice preview for interpreter-derived invoice renders only when:
2. invoiceSuccess is false,
3. currentStep != customer,
4. currentStep == invoice,
5. invoiceFromInterpreter exists.
6. Gate at [frontend/src/App.jsx](frontend/src/App.jsx#L866).

### 6.4 Interpreter rendering rules

1. InterpreterPreview renders only when currentStep == interpreter and interpreterResult exists at [frontend/src/App.jsx](frontend/src/App.jsx#L858).
2. Interpreter actions availability is action-array driven in [frontend/src/InterpreterPreview.jsx](frontend/src/InterpreterPreview.jsx).

### 6.5 Success screen precedence

1. invoiceSuccess drives full success card render at [frontend/src/App.jsx](frontend/src/App.jsx#L831).
2. Auto-reset timer runs 10 seconds after invoiceSuccess in useEffect [frontend/src/App.jsx](frontend/src/App.jsx#L314).

### 6.6 Input behavior rules

1. Placeholder changes by currentStep customer mode at [frontend/src/App.jsx](frontend/src/App.jsx#L781).
2. Send action routes to customer parser branch only when currentStep == customer in [frontend/src/App.jsx](frontend/src/App.jsx#L495).
3. Otherwise send routes to conversational invoice endpoint.

---

## 7. Backend Responsibilities

### 7.1 app/agent/router.py

1. Entry point for conversational invoice agent messages.
2. Domain interception to customer flow when intent/session indicates customer mode.
3. Draft edit endpoint for partial updates.
4. Finalize endpoint for active draft finalization and PDF generation.

### 7.2 app/agent/agent_service.py

1. Main conversational invoice state machine.
2. Guarantees session and active draft lifecycle.
3. Performs branch-level parsing and update orchestration.
4. Produces AgentResponse with standardized fields and state.

### 7.3 app/agent/draft_service.py

1. Create draft invoice row.
2. Update draft row safely with recalculated GST summary.
3. Infer buyer state where possible.
4. Maintain denormalized buyer and seller columns.

### 7.4 app/customer/handler.py

1. In-memory per-session customer sub-state machine.
2. Optional field prompting and confirmation flow.
3. Persistence of customer and contact entities.
4. Customer preview payload contract generation.

### 7.5 app/agent/interpreter/*

1. OCR + parse + customer match + intent action suggestion pipeline.
2. Returns preview-only object with actions and confidence.

### 7.6 invoice/router.py and app/db/crud.py

1. Direct invoice creation without conversational draft dependency.
2. Invoice persistence and retrieval endpoints.

---

## 8. Data Contracts (customer_state, invoice payloads)

### 8.1 customer_state contract (in-memory)

Defined in [app/customer/handler.py](app/customer/handler.py#L35):

1. customer.name
2. customer.gstin
3. customer.phone
4. customer.email
5. customer.city
6. customer.state
7. awaiting
8. skipped_fields

### 8.2 AgentResponse contract

Defined in [app/agent/schemas.py](app/agent/schemas.py#L7):

1. message
2. agent_state
3. draft_invoice_id
4. invoice
5. missing_fields
6. warnings
7. next_expected_input

### 8.3 Customer preview payload contract

Generated by build_customer_preview in [app/customer/handler.py](app/customer/handler.py#L94):

1. type = customer_preview
2. data object: name, gstin, phone, email, city, state
3. ready boolean

Customer completion payloads:

1. type = customer_created with message in [app/customer/handler.py](app/customer/handler.py#L286) and [app/customer/handler.py](app/customer/handler.py#L319).

### 8.4 Draft invoice preview payload contract

Produced via _build_invoice_preview in [app/agent/invoice_helpers.py](app/agent/invoice_helpers.py#L61):

1. invoice_no
2. seller
3. buyer
4. items
5. subtotal
6. total_gst
7. cgst
8. sgst
9. igst
10. grand_total

### 8.5 Interpreter payload contract

From [app/agent/interpreter/service.py](app/agent/interpreter/service.py#L30):

1. message
2. customer object with type, name, phone, details
3. invoice object with items, gst, total
4. actions array
5. confidence
6. warnings array

### 8.6 Direct invoice create payload

Frontend request built in [frontend/src/App.jsx](frontend/src/App.jsx#L634), backend parsed in [invoice/router.py](invoice/router.py#L37):

1. invoice_date
2. seller.state
3. buyer.state
4. items[].description
5. items[].quantity
6. items[].unit_price
7. items[].gst_rate
8. buyer_name
9. buyer_state
10. seller_name
11. seller_state

---

## 9. Confirmation Logic

### 9.1 Customer confirmation logic

1. Conversational confirm keywords in customer handler route to _save_customer.
2. Direct frontend confirmation button bypasses conversational await-confirm and posts to /customer/create.
3. Cancel path clears customer session state and exits customer flow.

### 9.2 Invoice confirmation logic

1. Agent draft confirmation is explicit message confirm/accept/yes in agent service.
2. This moves to draft_created state if critical checks pass.
3. Finalization requires separate action:
4. either /agent/invoice/finalize with confirm true,
5. or direct /invoice/create in invoice step path.

### 9.3 Critical vs non-critical validation

1. Critical errors for confirm include no items or invalid quantity/price via _check_critical_validation_errors in [app/agent/invoice_helpers.py](app/agent/invoice_helpers.py#L89).
2. Non-critical warnings include buyer state, buyer gstin, buyer address, missing HSN via _get_non_critical_warnings in [app/agent/invoice_helpers.py](app/agent/invoice_helpers.py#L131).

---

## 10. Known Bugs / Lessons Learned

The following are known from repository stabilization notes and code behavior.

### 10.1 Stabilization fixes already applied

1. Invalid enum string in finalize path was corrected to AgentState enum.
2. Standalone create invoice path previously had a no-return gap; fixed by explicit return path.
3. Branch-level logging added in agent service for path traceability.
4. HSN branch now updates both hsn_code and hsn keys for compatibility.
5. Customer optional field extraction now persists awaited value before processing confirm.

Reference notes: [memories/repo/agent-stability-fixes.md](memories/repo/agent-stability-fixes.md).

### 10.2 Current risk points visible in code

1. Customer ID type contract drift risk remains documented in repo memory (UUID vs int expectations across layers).
2. Frontend customerDraft initial shape excludes city and state keys while optional completion checks include them in [frontend/src/App.jsx](frontend/src/App.jsx#L224) and [frontend/src/App.jsx](frontend/src/App.jsx#L349).
3. Frontend customer send parser does not extract city/state from free text in [frontend/src/App.jsx](frontend/src/App.jsx#L495), so allOptionalProcessed often depends on manual edits.
4. /customer/create request sends phone nullable from frontend [frontend/src/App.jsx](frontend/src/App.jsx#L391), while backend request model requires phone string in [app/customer/router.py](app/customer/router.py#L17). This can produce validation failures if phone is empty.

---

## 11. Rules to Prevent Breaking the System

### 11.1 State and response invariants

1. Never return raw strings for agent_state; always use AgentState enum values.
2. Preserve handle_message contract: every branch returns AgentResponse.
3. Keep currentStep values limited to interpreter, customer, invoice unless all render gates are updated.
4. Keep customer preview payload type markers unchanged: customer_preview and customer_created.

### 11.2 Rendering invariants

1. If adding new agent states, update all App render conditions and button guards.
2. Preserve hasInvoicePreview type filters; otherwise customer payloads may be rendered as invoice preview.
3. Any change to interpreter payload shape must be reflected in InterpreterPreview and buildInvoicePreviewFromInterpreter.

### 11.3 Persistence invariants

1. Maintain session_id -> active_draft_id consistency when creating/finalizing drafts.
2. Keep draft updates idempotent and recalculate GST summary after item or party changes.
3. Keep denormalized buyer/seller columns synced whenever buyer/seller JSON changes.
4. Preserve transaction boundaries for customer + contact inserts.

### 11.4 Contract invariants

1. Align customer ID types across ORM, schema, and frontend assumptions.
2. Align /customer/create request requirements with frontend nullable fields or enforce frontend validation before submit.
3. Do not rename payload keys used by frontend gate logic without coordinated update.

---

## 12. How to Debug Issues Using This Document

Use this as a deterministic troubleshooting workflow.

### 12.1 Step 1: Identify which flow failed

1. Interpreter issue: check upload endpoint and interpreterResult rendering gates.
2. Customer issue: check whether request routed through customer intent interception or direct /customer/create.
3. Invoice issue: check whether user is in agent draft track or direct create track.

### 12.2 Step 2: Validate state transitions first

1. Frontend: inspect agentState and currentStep values during failure.
2. Backend: inspect AgentResponse.agent_state and draft_invoice_id values.
3. Compare with expected gates in Section 6.

### 12.3 Step 3: Trace exact backend branch

1. Use branch logs in agent service to identify active branch.
2. If no branch log appears, verify router interception and endpoint path.
3. For customer flow, inspect awaiting and skipped_fields in CUSTOMER_STATE.

### 12.4 Step 4: Verify payload contracts

1. Validate response payload type markers for preview routing.
2. Validate invoice payload fields expected by InvoicePreview and finalize payload builder.
3. Validate customer request payload against backend validators.

### 12.5 Step 5: Confirm persistence behavior

1. Check whether db.flush/db.commit path executed for target flow.
2. For invoices, verify status and session_id/active_draft_id consistency.
3. For customer, verify both customer and customer_contacts rows were written.

### 12.6 Step 6: Common symptom-to-cause mapping

1. Confirm buttons missing: usually agentState or currentStep mismatch with render gates.
2. Customer flow unexpectedly routes to invoice agent: customer intent pattern did not match and no active customer session.
3. Draft seems lost: active_draft_id not set or cleared early.
4. Finalize fails with validation: critical errors from item quantity/price or missing draft.
5. UI not updating after valid backend response: payload shape does not match App applyAgentPayload switching rules.

### 12.7 Step 7: Safe fix protocol

1. Reproduce using the specific flow section in this document.
2. Patch only the failing branch and keep response contracts stable.
3. Re-test all gating conditions in App after backend changes.
4. Re-test both conversational and direct API variants where dual paths exist.
