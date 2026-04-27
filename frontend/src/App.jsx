import { useEffect, useState } from "react";
import InvoicePreview from "./InvoicePreview";
import InterpreterPreview from "./InterpreterPreview";

function CustomerPreview({
  customer,
  onChange,
  onBack,
  error = "",
}) {
  if (!customer) return null;

  return (
    <div style={customerPreviewStyles.card}>
      <h3 style={customerPreviewStyles.heading}>Customer Preview</h3>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>Name</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.name ?? ""}
          onChange={(e) => onChange?.("name", e.target.value)}
          placeholder="Enter customer name"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>Phone</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.phone ?? ""}
          onChange={(e) => onChange?.("phone", e.target.value)}
          placeholder="Enter phone"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>GSTIN</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.gstin ?? ""}
          onChange={(e) => onChange?.("gstin", e.target.value)}
          placeholder="Enter GSTIN"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>Email</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.email ?? ""}
          onChange={(e) => onChange?.("email", e.target.value)}
          placeholder="Enter email"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>Address</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.address ?? ""}
          onChange={(e) => onChange?.("address", e.target.value)}
          placeholder="Enter address"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>City</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.city ?? ""}
          onChange={(e) => onChange?.("city", e.target.value)}
          placeholder="Enter city"
        />
      </div>

      <div style={customerPreviewStyles.row}>
        <span style={customerPreviewStyles.label}>State</span>
        <input
          style={customerPreviewStyles.input}
          value={customer.state ?? ""}
          onChange={(e) => onChange?.("state", e.target.value)}
          placeholder="Enter state"
        />
      </div>

      {error && <p style={customerPreviewStyles.error}>{error}</p>}

      <div style={customerPreviewStyles.actionsRow}>
        <button type="button" style={customerPreviewStyles.secondaryButton} onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

const buildInvoicePreviewFromInterpreter = (result, customerId, customerData = null) => {
  if (!result?.invoice) {
    return null;
  }

  const invoice = result.invoice || {};
  const customer = { ...(result.customer || {}), ...(customerData || {}) };
  const gstRate = Number(invoice.gst) || 0;
  const items = Array.isArray(invoice.items)
    ? invoice.items.map((item) => ({
        description: item?.name ?? "",
        quantity: Number(item?.quantity) || 0,
        unit_price: Number(item?.price) || 0,
        gst_rate: gstRate,
      }))
    : [];

  const subtotal = items.reduce((sum, item) => sum + item.quantity * item.unit_price, 0);
  const gstTotal = (subtotal * gstRate) / 100;

  return {
    buyer: {
      id: customerId ?? undefined,
      name: customer.name ?? "",
      phone: customer.phone ?? "",
      gstin: customer.gstin ?? "",
      address: customer.address ?? "",
      state: customer.state ?? "",
      city: customer.city ?? "",
    },
    items,
    subtotal,
    grand_total: subtotal + gstTotal,
    cgst_amount: gstRate > 0 ? gstTotal / 2 : 0,
    sgst_amount: gstRate > 0 ? gstTotal / 2 : 0,
    igst_amount: 0,
  };
}

const customerPreviewStyles = {
  card: {
    width: "min(760px, calc(100vw - 48px))",
    marginTop: "20px",
    background: "rgba(18, 25, 38, 0.82)",
    border: "1px solid rgba(255, 255, 255, 0.14)",
    borderRadius: "16px",
    padding: "20px 24px",
    boxShadow: "0 14px 45px rgba(0, 0, 0, 0.35)",
  },
  heading: {
    margin: "0 0 14px 0",
    fontSize: "18px",
    fontWeight: "600",
    color: "#a8c4f5",
  },
  row: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    padding: "8px 0",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
  },
  label: {
    color: "rgba(245, 247, 251, 0.55)",
    fontWeight: "500",
    minWidth: "90px",
  },
  value: {
    color: "#f5f7fb",
    fontWeight: "500",
    flex: 1,
    textAlign: "right",
  },
  input: {
    flex: 1,
    borderRadius: "8px",
    border: "1px solid rgba(255, 255, 255, 0.2)",
    background: "rgba(255, 255, 255, 0.08)",
    color: "#f5f7fb",
    padding: "8px 10px",
    outline: "none",
    fontSize: "14px",
  },
  actionsRow: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "10px",
    marginTop: "14px",
  },
  primaryButton: {
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "8px",
    padding: "9px 12px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
  },
  secondaryButton: {
    background: "rgba(255, 255, 255, 0.08)",
    border: "1px solid rgba(255, 255, 255, 0.2)",
    color: "#f5f7fb",
    borderRadius: "8px",
    padding: "9px 12px",
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
  },
  error: {
    margin: "10px 0 0 0",
    color: "#ffb4b4",
    fontSize: "13px",
  },
};

function App() {
  const createSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const [sessionId, setSessionId] = useState(createSessionId());

  const [message, setMessage] = useState("");
  const [agentResponse, setAgentResponse] = useState("");
  const [agentState, setAgentState] = useState("");
  const [draftPreview, setDraftPreview] = useState(null);
  const [customerPreview, setCustomerPreview] = useState(null);
  const [customerSuccess, setCustomerSuccess] = useState("");
  const [invoiceSuccess, setInvoiceSuccess] = useState("");
  const [draftSuccess, setDraftSuccess] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);
  const [draftInvoiceId, setDraftInvoiceId] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [showInvoicesPanel, setShowInvoicesPanel] = useState(false);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [invoicesError, setInvoicesError] = useState("");
  const [interpreterResult, setInterpreterResult] = useState(null);
  const [interpreterLoading, setInterpreterLoading] = useState(false);
  const [interpreterError, setInterpreterError] = useState("");
  const [editableInvoice, setEditableInvoice] = useState(null);
  const [openedInvoiceId, setOpenedInvoiceId] = useState(null);
  const [invoiceMode, setInvoiceMode] = useState(null);
  const [customer_id, setCustomer_id] = useState(null);
  const [currentStep, setCurrentStep] = useState("interpreter");
  const [customerFlowOrigin, setCustomerFlowOrigin] = useState("standalone");
  const [customerDraft, setCustomerDraft] = useState({
    name: "",
    phone: "",
    email: "",
    address: "",
    gstin: "",
    state: "",
    city: "",
  });
  const [customerCreateLoading, setCustomerCreateLoading] = useState(false);
  const [customerCreateError, setCustomerCreateError] = useState("");

  const applyAgentPayload = (data) => {
    const nextState = data.agent_state ?? "";

    if (nextState === "finalized") {
      resetSessionFlow();
      return;
    }

    setAgentResponse(data.message ?? "");
    setAgentState(nextState);

    const previewPayload = data.invoice ?? data.data ?? null;
    if (previewPayload?.type === "customer_preview") {
      setCustomerDraft(previewPayload.data ?? { name: "", phone: "", email: "", address: "", gstin: "" });
      setCustomerFlowOrigin("standalone");
      setCurrentStep("customer");
      setCustomerPreview(previewPayload.data ?? null);
      setCustomerSuccess("");
      setDraftPreview(null);
      setDraftInvoiceId(null);
    } else if (previewPayload?.type === "customer_created") {
      setCustomerSuccess(previewPayload.message ?? "Customer created successfully.");
      setCustomerPreview(null);
      setDraftPreview(null);
      setDraftInvoiceId(null);
    } else {
      setCustomerPreview(null);
      setCustomerSuccess("");
      setDraftPreview(data.draft ?? previewPayload ?? data);
      setEditableInvoice(data.draft ?? previewPayload ?? data);
      setDraftInvoiceId(data.draft_invoice_id ?? null);
    }
  };

  const fetchInvoices = async () => {
    try {
      setInvoicesLoading(true);
      setInvoicesError("");

      const response = await fetch("http://127.0.0.1:8000/invoice/");
      if (!response.ok) {
        throw new Error(`Failed to fetch invoices (${response.status})`);
      }

      const data = await response.json();
      setInvoices(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Error fetching invoices:", error);
      setInvoicesError("Unable to load invoices. Please try again.");
    } finally {
      setInvoicesLoading(false);
    }
  };

  const resetSessionFlow = () => {
    setSessionId(createSessionId());
    setDraftInvoiceId(null);
    setDraftPreview(null);
    setCustomerPreview(null);
    setCustomerSuccess("");
    setInvoiceSuccess("");
    setDraftSuccess(false);
    setDraftSaved(false);
    setAgentState("");
    setAgentResponse("");
    setMessage("");
    setInterpreterResult(null);
    setInterpreterError("");
    setInterpreterLoading(false);
    setEditableInvoice(null);
    setOpenedInvoiceId(null);
    setInvoiceMode(null);
    setCustomer_id(null);
    setCurrentStep("interpreter");
    setCustomerDraft({ name: "", phone: "", email: "", address: "", gstin: "" });
    setCustomerCreateLoading(false);
    setCustomerCreateError("");
  };

  useEffect(() => {
    if (!invoiceSuccess) {
      return;
    }

    const timerId = setTimeout(() => {
      resetSessionFlow();
    }, 10000);

    return () => {
      clearTimeout(timerId);
    };
  }, [invoiceSuccess]);

  const handleCustomerDraftChange = (field, value) => {
    setCustomerDraft((prev) => ({ ...prev, [field]: value }));
  };

  const handleAddCustomerStep = () => {
    const interpretedCustomer = interpreterResult?.customer || {};
    const interpretedDetails = interpretedCustomer.details || {};
    const prefill = {
      name: interpretedCustomer.name ?? "",
      phone: interpretedCustomer.phone ?? "",
      email: interpretedCustomer.email ?? interpretedDetails.email ?? "",
      address: interpretedCustomer.address ?? interpretedDetails.address ?? "",
      gstin: interpretedCustomer.gstin ?? interpretedDetails.gstin ?? "",
    };
    setCustomerDraft(prefill);
    setCustomerFlowOrigin("interpreter");
    setCustomerCreateError("");
    setCurrentStep("customer");

    const optionalFields = ["gstin", "phone", "email", "city", "state"];
    const allOptionalProcessed = optionalFields.every((field) => {
      const value = prefill[field];
      return typeof value === "string" && value.trim().length > 0;
    });

    if (prefill.name?.trim() && allOptionalProcessed) {
      setAgentState("awaiting_confirmation");
      setAgentResponse("Customer information is ready. Please review the live preview and confirm.");
      return;
    }

    setAgentState("collecting_info");
    if (!prefill.name?.trim()) {
      setAgentResponse("I prefilled customer details from the image. Please provide customer name to continue.");
      return;
    }

    setAgentResponse("I prefilled customer details from the image. You can keep adding optional details or type 'confirm', 'create', or 'done' when ready.");
  };

  const handleConfirmCustomer = async () => {
    if (!customerDraft.name?.trim()) {
      setCustomerCreateError("Customer name is required.");
      return;
    }

    try {
      setCustomerCreateLoading(true);
      setCustomerCreateError("");

      const response = await fetch("http://127.0.0.1:8000/customer/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(customerDraft),
      });

      if (!response.ok) {
        let detail = `Customer create failed (${response.status})`;
        try {
          const errorPayload = await response.json();
          if (errorPayload?.detail) {
            detail = String(errorPayload.detail);
          }
        } catch {
          // Keep fallback detail if body is not JSON.
        }
        throw new Error(detail);
      }

      const data = await response.json();
      console.log("CREATE CUSTOMER RESPONSE:", data);
      applyAgentPayload(data);
      const createdCustomerPayload = data?.customer ?? data?.data ?? null;
      const createdCustomer = {
        id: createdCustomerPayload?.id ?? null,
        name: (createdCustomerPayload?.name ?? customerDraft.name?.trim()) || null,
        phone: (createdCustomerPayload?.phone ?? customerDraft.phone?.trim()) || null,
        gstin: (createdCustomerPayload?.gstin ?? customerDraft.gstin?.trim()) || null,
        address: (createdCustomerPayload?.address ?? customerDraft.address?.trim()) || null,
        state: (createdCustomerPayload?.state ?? customerDraft.state?.trim()) || null,
        city: (createdCustomerPayload?.city ?? customerDraft.city?.trim()) || null,
      };
      const createdCustomerId = createdCustomer?.id ?? null;
      setCustomer_id(createdCustomerId);

      if (customerFlowOrigin === "standalone") {
        setTimeout(() => {
          setCustomerDraft({});
          setCurrentStep(null);
          setCustomerSuccess("");
          setAgentState("");
        }, 3000);
      } else {
        const parsed = buildInvoicePreviewFromInterpreter(interpreterResult, createdCustomerId, createdCustomer);
        setEditableInvoice(parsed ?? null);
        setCurrentStep("invoice");
      }

    } catch (error) {
      console.error("Error creating customer:", error);
      setCustomerCreateError(error.message || "Failed to create customer.");
    } finally {
      setCustomerCreateLoading(false);
    }
  };

  const handleCreateInvoiceStep = () => {
    const customerType = interpreterResult?.customer?.type;
    if (customerType === "new") {
      alert("Please add customer first");
      return;
    }
    const parsed = buildInvoicePreviewFromInterpreter(interpreterResult, customer_id);
    setEditableInvoice(parsed ?? null);
    setCurrentStep("invoice");
  };

  const handleImageUpload = async (file) => {
    if (!file) {
      return;
    }

    try {
      setInterpreterLoading(true);
      setInterpreterError("");
      setInterpreterResult(null);

      const formData = new FormData();
      formData.append("image", file);

      const response = await fetch("http://127.0.0.1:8000/agent/interpreter", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let detail = `Interpreter request failed (${response.status})`;
        try {
          const errorPayload = await response.json();
          if (errorPayload?.detail) {
            detail = String(errorPayload.detail);
          }
        } catch {
          // Keep fallback detail if response body is not JSON.
        }
        throw new Error(detail);
      }

      const data = await response.json();
      setInterpreterResult(data);
      setCurrentStep("interpreter");
      setCustomerPreview(null);
      setCustomerSuccess("");
      setInvoiceSuccess("");
      setOpenedInvoiceId(null);
      setInvoiceMode(null);
      setCustomer_id(null);
      setCustomerCreateError("");
      console.log("Interpreter response:", data);
    } catch (error) {
      console.error("Error uploading image:", error);
      setInterpreterError(error.message || "Failed to process image.");
    } finally {
      setInterpreterLoading(false);
    }
  };

  const handleSend = async () => {
    // Handle customer collection flow
    if (currentStep === "customer") {
      // Parse customer message for phone/name/email/etc
      const userInput = message.trim();
      const userInputLower = userInput.toLowerCase();
      const normalizedInput = userInputLower.replace(/\s+/g, " ").trim();
      const updatedDraft = { ...customerDraft };
      const confirmIntents = new Set(["confirm", "create", "done"]);
      const explicitConfirm = confirmIntents.has(normalizedInput);
      
      // Try to extract phone (10 digits starting with 6-9)
      const phoneMatch = userInput.match(/[6-9]\d{9}/);
      if (phoneMatch) {
        updatedDraft.phone = phoneMatch[0];
      }
      
      // Try to extract email
      const emailMatch = userInput.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
      if (emailMatch && !userInputLower.includes("phone")) {
        updatedDraft.email = emailMatch[0];
      }
      
      // Try to extract GSTIN (format: 2 digits, 2 letters, 5 alphanumeric, 1 letter)
      const gstinMatch = userInput.match(/\d{2}[A-Z]{2}[A-Z0-9]{5}[A-Z]{1}/);
      if (gstinMatch) {
        updatedDraft.gstin = gstinMatch[0];
      }
      
      // Try to extract name (if user started with "my name is..." or "name: ...")
      if (userInputLower.includes("my name") || userInputLower.includes("name is")) {
        const nameMatch = userInput.match(/(?:my )?name (?:is )?(.+?)(?:,|$)/i);
        if (nameMatch && nameMatch[1]) {
          updatedDraft.name = nameMatch[1].trim();
        }
      }
      
      // Update the draft with any extracted information
      setCustomerDraft(updatedDraft);

      const optionalFields = ["gstin", "phone", "email", "city", "state"];
      const allOptionalProcessed = optionalFields.every((field) => {
        const value = updatedDraft[field];
        return typeof value === "string" && value.trim().length > 0;
      });

      if (explicitConfirm || allOptionalProcessed) {
        setAgentState("awaiting_confirmation");
        setAgentResponse("Great, all required customer details are filled. Review the preview and confirm.");
        setMessage("");
        return;
      }

      if (!updatedDraft.name?.trim()) {
        setAgentState("collecting_info");
        setAgentResponse("Please provide customer name to continue.");
        setMessage("");
        return;
      }

      setAgentState("collecting_info");
      if (phoneMatch || emailMatch || gstinMatch) {
        setAgentResponse("Got it. You can add more optional details, or type 'confirm', 'create', or 'done' to continue.");
      } else {
        setAgentResponse("You can add optional details (GSTIN, phone, email, city, state), or type 'confirm', 'create', or 'done' to continue.");
      }
      setMessage("");
      return;
    }

    // Regular agent flow (invoice/draft)
    try {
      const response = await fetch("http://127.0.0.1:8000/agent/invoice/draft", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message,
        }),
      });

      if (!response.ok) {
        throw new Error(`Draft request failed (${response.status})`);
      }

      const data = await response.json();
      applyAgentPayload(data);
      setMessage("");
      console.log("Draft response:", data);
    } catch (error) {
      console.error("Error sending draft request:", error);
    }
  };

  const handleFinalize = async () => {
    try {
      if (currentStep === "invoice") {
        const activeInvoice = editableInvoice;

        if (!activeInvoice) {
          throw new Error("Invoice data is not available.");
        }

        const buyerState = (activeInvoice?.buyer?.state ?? "").trim();
        const sellerState = (activeInvoice?.seller?.state ?? "").trim() || buyerState;

        if (!buyerState) {
          throw new Error("Buyer state is required.");
        }

        const payload = {
          invoice_date: new Date().toISOString().slice(0, 10),
          seller: {
            name: activeInvoice?.seller?.name ?? "Your Company",
            state: sellerState,
          },
          buyer: {
            name: activeInvoice?.buyer?.name ?? "",
            gstin: activeInvoice?.buyer?.gstin ?? "",
            address: activeInvoice?.buyer?.address ?? "",
            state: buyerState,
          },
          items: Array.isArray(activeInvoice?.items)
            ? activeInvoice.items.map((item) => ({
                description: item?.description ?? "",
                quantity: Number(item?.quantity) || 0,
                unit_price: Number(item?.unit_price) || 0,
                gst_rate: Number(item?.gst_rate) || 0,
              }))
            : [],
          buyer_name: activeInvoice?.buyer?.name ?? "",
          buyer_state: buyerState,
          seller_name: activeInvoice?.seller?.name ?? "Your Company",
          seller_state: sellerState,
        };

        console.log("FINAL PAYLOAD:", payload);

        const response = await fetch("http://127.0.0.1:8000/invoice/create", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(`Failed to finalize invoice (${response.status})`);
        }

        const data = await response.json();
        console.log("Finalize response:", data);

        await fetchInvoices();

        setInvoiceSuccess(data?.message ?? "Invoice created successfully.");
        return;
      }

      const response = await fetch("http://127.0.0.1:8000/agent/invoice/finalize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          confirm: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to finalize invoice (${response.status})`);
      }

      const data = await response.json();
      console.log("Finalize response:", data);

      // If invoices panel is open, refresh it so the newly finalized invoice appears immediately.
      if (showInvoicesPanel) {
        await fetchInvoices();
      }

      setInvoiceSuccess(data?.message ?? "Invoice finalized successfully.");
    } catch (error) {
      console.error("Error sending finalize request:", error);
    }
  };

  const handleSaveDraft = async () => {
    try {
      if (!editableInvoice) {
        throw new Error("Invoice data is not available.");
      }

      if (openedInvoiceId) {
        const response = await fetch("http://127.0.0.1:8000/agent/invoice/edit", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            draft_invoice_id: openedInvoiceId,
            updates: editableInvoice,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to save draft (${response.status})`);
        }

        const data = await response.json();
        applyAgentPayload(data);
        setDraftInvoiceId(data?.draft_invoice_id ?? openedInvoiceId);
        setDraftSuccess(true);
        setDraftSaved(true);
        setTimeout(() => setDraftSuccess(false), 3000);
        return;
      }

      const response = await fetch("http://127.0.0.1:8000/agent/invoice/draft", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: "create invoice",
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create draft (${response.status})`);
      }

      const data = await response.json();
      applyAgentPayload(data);
      setOpenedInvoiceId(data?.draft_invoice_id ?? null);
      setDraftInvoiceId(data?.draft_invoice_id ?? null);
      setInvoiceMode("draft");
      setDraftSuccess(true);
      setDraftSaved(true);
      setTimeout(() => setDraftSuccess(false), 3000);
    } catch (error) {
      console.error("Error saving draft:", error);
    }
  };

  const handleInvoicesClick = async () => {
    const nextVisibility = !showInvoicesPanel;
    setShowInvoicesPanel(nextVisibility);

    // Fetch invoices only when opening the panel to keep calls minimal.
    if (!nextVisibility) {
      return;
    }

    await fetchInvoices();
  };

  const handleViewInvoices = async () => {
    setShowInvoicesPanel(true);
    await fetchInvoices();
  };

  const handleDownloadInvoice = (invoiceId) => {
    window.open(`http://127.0.0.1:8000/invoice/${invoiceId}/pdf`, "_blank");
  };

  const handleOpenInvoice = async (invoiceId) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/invoice/${invoiceId}`);

      if (!response.ok) {
        throw new Error(`Failed to open invoice (${response.status})`);
      }

      const invoice = await response.json();
      setEditableInvoice(invoice);
      setOpenedInvoiceId(invoice.id);
      setInvoiceMode("draft");
      setCurrentStep("invoice");
    } catch (error) {
      console.error("Error opening invoice:", error);
    }
  };

  const formatFinalizedAt = (value) => {
    if (!value) {
      return "-";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  };

  const isCustomerFlow = currentStep === "customer";

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>AI GST Invoice</h1>

      <div style={styles.toolbarRow}>
        <button onClick={handleInvoicesClick} style={styles.invoicesButton}>
          {showInvoicesPanel ? "Hide Invoices" : "Invoices"}
        </button>
      </div>

      <div style={styles.commandBar}>
        {/* Upload icon */}
        <label style={styles.iconButton}>
          +
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                await handleImageUpload(file);
              }
              // Allow selecting the same file again in subsequent attempts.
              e.target.value = "";
            }}
          />
        </label>

        {/* Text input */}
        <input
          type="text"
          placeholder={currentStep === "customer" ? "Share customer details to update preview live..." : "Type your invoice command..."}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          style={styles.input}
        />

        {/* Send icon */}
        <button onClick={handleSend} style={styles.sendButton}>
          ➤
        </button>
      </div>

      {agentState !== "draft_created" && <p>Agent: {agentResponse}</p>}
      {agentState === "draft_created" && (
        <div>
          <p>Draft created successfully.</p>
          <button onClick={handleFinalize}>Finalize Invoice</button>
        </div>
      )}
      {isCustomerFlow && customerDraft && (
        <CustomerPreview
          customer={customerDraft}
          onChange={handleCustomerDraftChange}
          onBack={() => setCurrentStep("interpreter")}
          error={customerCreateError}
        />
      )}
      {currentStep === "customer" && customerDraft?.name?.trim() && (
        <button
          type="button"
          style={{ ...customerPreviewStyles.primaryButton, marginTop: "16px" }}
          onClick={handleConfirmCustomer}
          disabled={customerCreateLoading}
        >
          {customerCreateLoading ? "Saving..." : "Confirm Customer"}
        </button>
      )}
      {customerSuccess && (
        <div style={{ marginTop: "16px", color: "#7defa1", fontWeight: "600", fontSize: "16px" }}>
          {customerSuccess}
        </div>
      )}

      {invoiceSuccess && (
        <div style={styles.successScreenContainer}>
          <div style={styles.successScreenCard}>
            <h2 style={styles.successScreenTitle}>Invoice Created 🎉</h2>
            <p style={styles.successScreenSubtitle}>Ready for your next command</p>
            <p style={styles.successRedirectText}>Redirecting in 10 seconds...</p>
            <div style={styles.successActionsRow}>
              <button style={styles.successPrimaryButton} onClick={resetSessionFlow}>
                ← Back to Home
              </button>
              <button style={styles.successSecondaryButton} onClick={handleViewInvoices}>
                View Invoices
              </button>
            </div>
          </div>
        </div>
      )}

      {interpreterLoading && (
        <p style={styles.panelMessage}>Processing image...</p>
      )}

      {interpreterError && (
        <p style={styles.panelError}>{interpreterError}</p>
      )}

      {currentStep === "interpreter" && interpreterResult && (
        <InterpreterPreview
          data={interpreterResult}
          onCreateInvoice={handleCreateInvoiceStep}
          onAddCustomer={handleAddCustomerStep}
        />
      )}

      {!isCustomerFlow && editableInvoice && !invoiceSuccess && draftSaved && (
        <div style={{ marginTop: "24px", textAlign: "center", width: "min(600px, calc(100vw - 48px))" }}>
          <h2 style={{ color: "#7defa1", fontSize: "24px", fontWeight: "700", margin: "0 0 8px 0" }}>Draft saved ✓</h2>
          <p style={{ color: "rgba(245,247,251,0.72)", fontSize: "14px", margin: "0 0 20px 0" }}>You can continue editing or finalize anytime</p>
          <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
            <button style={styles.finalizePreviewButton} type="button" onClick={() => setDraftSaved(false)}>
              Continue Editing
            </button>
            <button style={styles.finalizePreviewButton} type="button" onClick={handleViewInvoices}>
              View Drafts
            </button>
          </div>
        </div>
      )}

      {!isCustomerFlow && editableInvoice && !invoiceSuccess && !draftSaved && (
        <>
          <InvoicePreview
            invoice={editableInvoice}
            onInvoiceChange={setEditableInvoice}
          />
          <div style={{ display: "flex", gap: "10px", marginTop: "20px", width: "min(600px, calc(100vw - 48px))" }}>
            <button style={styles.finalizePreviewButton} type="button" onClick={handleSaveDraft}>
              {draftSuccess ? "Saved" : "Save as Draft"}
            </button>
            <button style={styles.finalizePreviewButton} onClick={handleFinalize}>
              Finalize Invoice
            </button>
          </div>
        </>
      )}

      {showInvoicesPanel && (
        <div style={styles.invoicesPanel}>
          <h2 style={styles.invoicesTitle}>Invoices</h2>

          {invoicesLoading && <p style={styles.panelMessage}>Loading invoices...</p>}
          {invoicesError && <p style={styles.panelError}>{invoicesError}</p>}

          {!invoicesLoading && !invoicesError && (
            <div style={styles.invoicesTableWrapper}>
              <table style={styles.invoicesTable}>
                <thead>
                  <tr>
                    <th style={styles.tableHeaderCell}>ID</th>
                    <th style={styles.tableHeaderCell}>Invoice Number</th>
                    <th style={styles.tableHeaderCell}>Buyer</th>
                    <th style={styles.tableHeaderCell}>Finalized At</th>
                    <th style={styles.tableHeaderCell}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.invoice_id}>
                      <td style={styles.tableCell}>{invoice.invoice_id}</td>
                      <td style={styles.tableCell}>{invoice.invoice_number}</td>
                      <td style={styles.tableCell}>{invoice.buyer_name ?? "-"}</td>
                      <td style={styles.tableCell}>{formatFinalizedAt(invoice.finalized_at)}</td>
                      <td style={styles.tableCell}>
                        {String(invoice?.invoice_number ?? "").startsWith("DRAFT") ? (
                          <button
                            style={styles.downloadButton}
                            onClick={() => handleOpenInvoice(invoice.invoice_id)}
                          >
                            Open
                          </button>
                        ) : (
                          <button
                            style={styles.downloadButton}
                            onClick={() => handleDownloadInvoice(invoice.invoice_id)}
                          >
                            Download
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {invoices.length === 0 && (
                <p style={styles.panelMessage}>No finalized invoices found.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    position: "relative",
    width: "100vw",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    background:
      "radial-gradient(circle at 50% 20%, #1a2334 0%, #0f1727 40%, #0a101a 100%)",
    color: "#f5f7fb",
    fontFamily: "Inter, Arial, sans-serif",
    padding: "24px",
    boxSizing: "border-box",
    overflowY: "auto",
  },
  title: {
    fontSize: "44px",
    marginBottom: "30px",
    fontWeight: "600",
    letterSpacing: "-0.02em",
  },
  toolbarRow: {
    width: "min(760px, calc(100vw - 48px))",
    display: "flex",
    justifyContent: "flex-end",
    marginBottom: "12px",
  },
  invoicesButton: {
    background: "rgba(255, 255, 255, 0.10)",
    border: "1px solid rgba(255, 255, 255, 0.18)",
    color: "#f5f7fb",
    borderRadius: "10px",
    padding: "10px 14px",
    fontSize: "14px",
    fontWeight: "600",
    cursor: "pointer",
  },
  commandBar: {
    display: "flex",
    alignItems: "center",
    width: "min(760px, calc(100vw - 48px))",
    background: "rgba(18, 25, 38, 0.82)",
    backdropFilter: "blur(14px)",
    border: "1px solid rgba(255, 255, 255, 0.14)",
    borderRadius: "22px",
    padding: "10px 12px 10px 10px",
    gap: "10px",
    boxShadow: "0 14px 45px rgba(0, 0, 0, 0.35)",
  },
  iconButton: {
    cursor: "pointer",
    width: "38px",
    height: "38px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "999px",
    color: "rgba(245, 247, 251, 0.95)",
    background: "rgba(255, 255, 255, 0.06)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    fontSize: "22px",
    lineHeight: 1,
    fontWeight: "300",
    userSelect: "none",
  },
  input: {
    flex: 1,
    background: "transparent",
    border: "none",
    outline: "none",
    color: "#f5f7fb",
    fontSize: "16px",
    lineHeight: "1.5",
    padding: "0 4px",
  },
  sendButton: {
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "999px",
    width: "38px",
    height: "38px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "17px",
    lineHeight: 1,
    cursor: "pointer",
    fontWeight: "700",
  },
  finalizePreviewButton: {
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "10px",
    padding: "10px 16px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
  },
  successScreenContainer: {
    width: "100%",
    marginTop: "20px",
    display: "flex",
    justifyContent: "center",
  },
  successScreenCard: {
    width: "min(620px, calc(100vw - 48px))",
    background: "linear-gradient(165deg, rgba(30, 48, 41, 0.92) 0%, rgba(18, 30, 52, 0.92) 100%)",
    border: "1px solid rgba(125, 239, 161, 0.32)",
    borderRadius: "18px",
    padding: "28px 24px",
    boxShadow: "0 22px 58px rgba(0, 0, 0, 0.36)",
    textAlign: "center",
  },
  successScreenTitle: {
    margin: 0,
    fontSize: "30px",
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
    color: "#f5f7fb",
    fontWeight: "700",
  },
  successScreenSubtitle: {
    margin: "10px 0 0 0",
    color: "rgba(245, 247, 251, 0.78)",
    fontSize: "16px",
  },
  successRedirectText: {
    margin: "8px 0 0 0",
    color: "rgba(245, 247, 251, 0.62)",
    fontSize: "13px",
  },
  successActionsRow: {
    marginTop: "22px",
    display: "flex",
    justifyContent: "center",
    gap: "12px",
    alignItems: "center",
    flexWrap: "wrap",
  },
  successPrimaryButton: {
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "10px",
    padding: "10px 14px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  successSecondaryButton: {
    background: "rgba(255, 255, 255, 0.08)",
    border: "1px solid rgba(255, 255, 255, 0.2)",
    color: "#f5f7fb",
    borderRadius: "10px",
    padding: "10px 14px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  invoicesPanel: {
    width: "min(980px, calc(100vw - 48px))",
    marginTop: "24px",
    background: "rgba(18, 25, 38, 0.82)",
    border: "1px solid rgba(255, 255, 255, 0.14)",
    borderRadius: "16px",
    padding: "16px",
    boxShadow: "0 14px 45px rgba(0, 0, 0, 0.35)",
  },
  invoicesTitle: {
    margin: "0 0 12px 0",
    fontSize: "24px",
    fontWeight: "600",
  },
  panelMessage: {
    margin: "8px 0",
    color: "rgba(245, 247, 251, 0.85)",
  },
  panelError: {
    margin: "8px 0",
    color: "#ffb4b4",
  },
  invoicesTableWrapper: {
    maxHeight: "420px",
    overflowY: "auto",
    border: "1px solid rgba(255, 255, 255, 0.10)",
    borderRadius: "12px",
  },
  invoicesTable: {
    width: "100%",
    borderCollapse: "collapse",
    minWidth: "760px",
  },
  tableHeaderCell: {
    textAlign: "left",
    padding: "10px 12px",
    fontSize: "13px",
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    color: "rgba(245, 247, 251, 0.72)",
    borderBottom: "1px solid rgba(255, 255, 255, 0.10)",
    position: "sticky",
    top: 0,
    background: "rgba(18, 25, 38, 0.95)",
    backdropFilter: "blur(8px)",
    zIndex: 1,
  },
  tableCell: {
    padding: "10px 12px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
    fontSize: "14px",
    color: "#f5f7fb",
  },
  downloadButton: {
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "8px",
    padding: "8px 12px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
  },
};

export default App;
