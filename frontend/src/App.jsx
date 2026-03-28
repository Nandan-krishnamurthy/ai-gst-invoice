import { useState } from "react";
import InvoicePreview from "./InvoicePreview";

function CustomerPreview({ customer }) {
  if (!customer) return null;
  const fields = [
    { label: "Name", value: customer.name },
    { label: "GSTIN", value: customer.gstin },
    { label: "Phone", value: customer.phone },
    { label: "Email", value: customer.email },
    { label: "City", value: customer.city },
    { label: "State", value: customer.state },
  ];
  return (
    <div style={customerPreviewStyles.card}>
      <h3 style={customerPreviewStyles.heading}>Customer Details</h3>
      {fields.map(({ label, value }) => (
        <div key={label} style={customerPreviewStyles.row}>
          <span style={customerPreviewStyles.label}>{label}</span>
          <span style={customerPreviewStyles.value}>{value ?? <em style={{ opacity: 0.4 }}>—</em>}</span>
        </div>
      ))}
    </div>
  );
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
    justifyContent: "space-between",
    padding: "6px 0",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
    fontSize: "15px",
  },
  label: {
    color: "rgba(245, 247, 251, 0.55)",
    fontWeight: "500",
    minWidth: "90px",
  },
  value: {
    color: "#f5f7fb",
    textAlign: "right",
    wordBreak: "break-all",
  },
};

function App() {
  const createSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const [sessionId, setSessionId] = useState(createSessionId());

  const [message, setMessage] = useState("");
  const [agentResponse, setAgentResponse] = useState("");
  const [agentState, setAgentState] = useState("");
  const [draftPreview, setDraftPreview] = useState(null);
  const [invoicePreview, setInvoicePreview] = useState(null);
  const [customerPreview, setCustomerPreview] = useState(null);
  const [customerSuccess, setCustomerSuccess] = useState("");
  const [draftInvoiceId, setDraftInvoiceId] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [showInvoicesPanel, setShowInvoicesPanel] = useState(false);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [invoicesError, setInvoicesError] = useState("");

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
      setCustomerPreview(previewPayload.data ?? null);
      setCustomerSuccess("");
      setInvoicePreview(null);
      setDraftPreview(null);
      setDraftInvoiceId(null);
    } else if (previewPayload?.type === "customer_created") {
      setCustomerSuccess(previewPayload.message ?? "Customer created successfully.");
      setCustomerPreview(null);
      setInvoicePreview(null);
      setDraftPreview(null);
      setDraftInvoiceId(null);
    } else {
      setInvoicePreview(previewPayload);
      setCustomerPreview(null);
      setCustomerSuccess("");
      setDraftPreview(data.draft ?? previewPayload ?? data);
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
    setInvoicePreview(null);
    setDraftInvoiceId(null);
    setDraftPreview(null);
    setCustomerPreview(null);
    setCustomerSuccess("");
    setAgentState("");
    setAgentResponse("");
    setMessage("");
  };

  const handleSend = async () => {
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

  const handleAccept = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/agent/invoice/draft", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: "confirm",
        }),
      });

      if (!response.ok) {
        throw new Error(`Confirm request failed (${response.status})`);
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

      resetSessionFlow();
    } catch (error) {
      console.error("Error sending finalize request:", error);
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

  const handleDownloadInvoice = (invoiceId) => {
    window.open(`http://127.0.0.1:8000/invoice/${invoiceId}/pdf`, "_blank");
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
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files[0];
              if (file) {
                console.log("Selected file:", file.name);
              }
            }}
          />
        </label>

        {/* Text input */}
        <input
          type="text"
          placeholder="Type your invoice command..."
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
      {invoicePreview && invoicePreview.type !== "customer_preview" && invoicePreview.type !== "customer_created" && (
        <InvoicePreview invoice={invoicePreview} />
      )}
      {customerPreview && (
        <CustomerPreview customer={customerPreview} />
      )}
      {agentState === "awaiting_confirmation" && (invoicePreview || customerPreview) && (
        <button style={{ marginTop: "16px" }} onClick={handleAccept}>
          {customerPreview ? "Confirm Customer" : "Confirm Invoice"}
        </button>
      )}
      {customerSuccess && (
        <div style={{ marginTop: "16px", color: "#7defa1", fontWeight: "600", fontSize: "16px" }}>
          {customerSuccess}
        </div>
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
                        <button
                          style={styles.downloadButton}
                          onClick={() => handleDownloadInvoice(invoice.invoice_id)}
                        >
                          Download
                        </button>
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
