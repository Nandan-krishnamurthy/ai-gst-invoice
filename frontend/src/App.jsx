import { useState } from "react";
import InvoicePreview from "./InvoicePreview";

function App() {
  const createSessionId = () => `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const [sessionId, setSessionId] = useState(createSessionId());

  const [message, setMessage] = useState("");
  const [agentResponse, setAgentResponse] = useState("");
  const [agentState, setAgentState] = useState("");
  const [draftPreview, setDraftPreview] = useState(null);
  const [invoicePreview, setInvoicePreview] = useState(null);
  const [draftInvoiceId, setDraftInvoiceId] = useState(null);

  const resetSessionFlow = () => {
    setSessionId(createSessionId());
    setInvoicePreview(null);
    setDraftInvoiceId(null);
    setDraftPreview(null);
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

      const data = await response.json();
      const nextState = data.agent_state ?? "";
      if (nextState === "finalized") {
        resetSessionFlow();
      } else {
        setAgentResponse(data.message ?? "");
        setAgentState(nextState);
        setDraftPreview(data.draft ?? data.invoice ?? data);
        setInvoicePreview(data.invoice ?? null);
        setDraftInvoiceId(data.draft_invoice_id ?? null);
      }
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

      const data = await response.json();
      const nextState = data.agent_state ?? "";
      if (nextState === "finalized") {
        resetSessionFlow();
      } else {
        setAgentResponse(data.message ?? "");
        setAgentState(nextState);
        if (data.invoice) {
          setInvoicePreview(data.invoice);
        }
        setDraftInvoiceId(data.draft_invoice_id ?? null);
      }
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

      const data = await response.json();
      console.log("Finalize response:", data);
      resetSessionFlow();
    } catch (error) {
      console.error("Error sending finalize request:", error);
    }
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>AI GST Invoice</h1>

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
      {invoicePreview && (
        <InvoicePreview invoice={invoicePreview} agentState={agentState} onAccept={handleAccept} />
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
};

export default App;
