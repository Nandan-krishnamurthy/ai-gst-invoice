function InvoicePreview({ invoice, agentState, onAccept }) {
  if (!invoice) {
    return null;
  }

  // Extract data with optional chaining and fallbacks
  const buyerName = invoice?.buyer?.name ?? invoice?.buyer_name ?? "";
  const buyerGstin = invoice?.buyer?.gstin ?? invoice?.buyer_gstin ?? "";
  const buyerAddress = invoice?.buyer?.address ?? invoice?.buyer_address ?? "";
  const buyerState = invoice?.buyer?.state ?? invoice?.buyer_state ?? "";
  
  const items = invoice?.items ?? invoice?.line_items ?? [];
  
  const displaySubtotal = invoice?.subtotal ?? invoice?.gst_summary?.subtotal ?? 0;
  const displayTotal = invoice?.grand_total ?? invoice?.gst_summary?.grand_total ?? 0;
  const cgstAmount = invoice?.cgst_amount ?? invoice?.gst_summary?.cgst ?? 0;
  const sgstAmount = invoice?.sgst_amount ?? invoice?.gst_summary?.sgst ?? 0;
  const igstAmount = invoice?.igst_amount ?? invoice?.gst_summary?.igst ?? 0;

  return (
    <div style={styles.container}>
      <div style={styles.previewCard}>
        <h2 style={styles.cardTitle}>Invoice Preview</h2>

        {/* Buyer Section */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Buyer</h3>
          <div style={styles.sectionContent}>
            {buyerName && (
              <div style={styles.row}>
                <span style={styles.label}>Name:</span>
                <span style={styles.value}>{buyerName}</span>
              </div>
            )}
            {buyerGstin && (
              <div style={styles.row}>
                <span style={styles.label}>GSTIN:</span>
                <span style={styles.value}>{buyerGstin}</span>
              </div>
            )}
            {buyerAddress && (
              <div style={styles.row}>
                <span style={styles.label}>Address:</span>
                <span style={styles.value}>{buyerAddress}</span>
              </div>
            )}
            {buyerState && (
              <div style={styles.row}>
                <span style={styles.label}>State:</span>
                <span style={styles.value}>{buyerState}</span>
              </div>
            )}
          </div>
        </div>

        {/* Items Section */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Items</h3>
          <div style={styles.itemsContainer}>
            {items.map((item, index) => (
              <div key={item?.id ?? item?.sku ?? index} style={styles.itemCard}>
                {item?.description && (
                  <div style={styles.row}>
                    <span style={styles.label}>Description:</span>
                    <span style={styles.value}>{item.description}</span>
                  </div>
                )}
                <div style={styles.row}>
                  <span style={styles.label}>HSN:</span>
                  <span style={styles.value}>
                    {item?.hsn ?? item?.hsn_code ?? "-"}
                  </span>
                </div>
                {item?.quantity !== undefined && (
                  <div style={styles.row}>
                    <span style={styles.label}>Quantity:</span>
                    <span style={styles.value}>{item.quantity}</span>
                  </div>
                )}
                {item?.unit_price !== undefined || item?.unitPrice !== undefined ? (
                  <div style={styles.row}>
                    <span style={styles.label}>Unit Price:</span>
                    <span style={styles.value}>
                      ₹{(item?.unit_price ?? item?.unitPrice ?? 0).toFixed(2)}
                    </span>
                  </div>
                ) : null}
                {item?.gst_rate !== undefined || item?.gstRate !== undefined ? (
                  <div style={styles.row}>
                    <span style={styles.label}>GST %:</span>
                    <span style={styles.value}>
                      {(item?.gst_rate ?? item?.gstRate ?? 0)}%
                    </span>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        {/* Summary Section */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Summary</h3>
          <div style={styles.summaryContent}>
            <div style={styles.summaryRow}>
              <span style={styles.label}>Subtotal:</span>
              <span style={styles.value}>₹{displaySubtotal.toFixed(2)}</span>
            </div>
            {igstAmount > 0 ? (
              <div style={styles.summaryRow}>
                <span style={styles.label}>IGST:</span>
                <span style={styles.value}>₹{igstAmount.toFixed(2)}</span>
              </div>
            ) : (
              <>
                <div style={styles.summaryRow}>
                  <span style={styles.label}>CGST:</span>
                  <span style={styles.value}>₹{cgstAmount.toFixed(2)}</span>
                </div>
                <div style={styles.summaryRow}>
                  <span style={styles.label}>SGST:</span>
                  <span style={styles.value}>₹{sgstAmount.toFixed(2)}</span>
                </div>
              </>
            )}
            <div style={{ ...styles.summaryRow, ...styles.totalRow }}>
              <span style={styles.label}>Total:</span>
              <span style={styles.totalValue}>₹{displayTotal.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* Accept Button */}
        {agentState === "awaiting_confirmation" && (
          <button style={styles.acceptButton} onClick={onAccept}>
            Accept
          </button>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    width: "100%",
    maxWidth: "600px",
    margin: "20px auto",
  },
  previewCard: {
    background: "rgba(18, 25, 38, 0.82)",
    border: "1px solid rgba(255, 255, 255, 0.14)",
    borderRadius: "16px",
    padding: "24px",
    boxShadow: "0 14px 45px rgba(0, 0, 0, 0.35)",
    color: "#f5f7fb",
    fontFamily: "Inter, Arial, sans-serif",
  },
  cardTitle: {
    fontSize: "24px",
    fontWeight: "600",
    marginBottom: "24px",
    color: "#f5f7fb",
    margin: "0 0 24px 0",
  },
  section: {
    marginBottom: "24px",
    paddingBottom: "16px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  },
  sectionTitle: {
    fontSize: "14px",
    fontWeight: "600",
    color: "rgba(245, 247, 251, 0.7)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "12px",
    margin: "0 0 12px 0",
  },
  sectionContent: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "14px",
    lineHeight: "1.5",
  },
  label: {
    color: "rgba(245, 247, 251, 0.6)",
    fontWeight: "500",
  },
  value: {
    color: "#f5f7fb",
    fontWeight: "400",
  },
  itemsContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  itemCard: {
    background: "rgba(255, 255, 255, 0.06)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: "8px",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  summaryContent: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  summaryRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "14px",
    lineHeight: "1.5",
  },
  totalRow: {
    marginTop: "8px",
    paddingTop: "10px",
    borderTop: "1px solid rgba(255, 255, 255, 0.08)",
    fontSize: "16px",
    fontWeight: "600",
  },
  totalValue: {
    color: "#e8edf7",
    fontWeight: "700",
  },
  acceptButton: {
    width: "100%",
    background: "#e8edf7",
    border: "none",
    color: "#0f1727",
    borderRadius: "8px",
    padding: "12px 16px",
    fontSize: "16px",
    fontWeight: "700",
    cursor: "pointer",
    marginTop: "24px",
    transition: "opacity 0.2s ease",
  },
};

export default InvoicePreview;
