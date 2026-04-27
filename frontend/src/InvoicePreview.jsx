import { useEffect, useState } from "react";

const toNumber = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const normalizeInvoice = (invoice) => {
  if (!invoice) {
    return null;
  }

  return {
    ...invoice,
    seller: {
      ...(invoice?.seller ?? {}),
      state: invoice?.seller?.state ?? invoice?.seller_state ?? "",
    },
    buyer: {
      ...(invoice?.buyer ?? {}),
      state: invoice?.buyer?.state ?? invoice?.buyer_state ?? "",
    },
    items: Array.isArray(invoice?.items ?? invoice?.line_items)
      ? (invoice.items ?? invoice.line_items).map((item) => ({
          ...item,
          description: item?.description ?? item?.name ?? "",
          quantity: toNumber(item?.quantity),
          unit_price: toNumber(item?.unit_price ?? item?.unitPrice ?? item?.price),
          gst_rate: toNumber(item?.gst_rate ?? item?.gstRate),
        }))
      : [],
  };
};

const calculateSummary = (invoice) => {
  const items = Array.isArray(invoice?.items) ? invoice.items : [];
  const subtotal = items.reduce(
    (sum, item) => sum + toNumber(item.quantity) * toNumber(item.unit_price),
    0,
  );
  const totalGst = items.reduce(
    (sum, item) => sum + (toNumber(item.quantity) * toNumber(item.unit_price) * toNumber(item.gst_rate)) / 100,
    0,
  );
  const sellerState = (invoice?.seller?.state ?? "").trim().toLowerCase();
  const buyerState = (invoice?.buyer?.state ?? "").trim().toLowerCase();
  const isInterState = Boolean(sellerState && buyerState) && sellerState !== buyerState;

  return {
    subtotal,
    grand_total: subtotal + totalGst,
    cgst_amount: isInterState ? 0 : totalGst / 2,
    sgst_amount: isInterState ? 0 : totalGst / 2,
    igst_amount: isInterState ? totalGst : 0,
  };
};

function InvoicePreview({ invoice, onInvoiceChange }) {
  if (!invoice) {
    return null;
  }

  const isEditable = typeof onInvoiceChange === "function";
  const [localInvoice, setLocalInvoice] = useState(() => normalizeInvoice(invoice));

  useEffect(() => {
    setLocalInvoice(normalizeInvoice(invoice));
  }, [invoice]);

  const updateInvoice = (updater) => {
    const next = typeof updater === "function" ? updater(localInvoice) : updater;
    setLocalInvoice(next);
    if (isEditable) {
      onInvoiceChange(next);
    }
  };

  const handleItemChange = (index, field, value) => {
    updateInvoice((prev) => ({
      ...prev,
      items: prev.items.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    }));
  };

  // Extract data with optional chaining and fallbacks
  const activeInvoice = localInvoice ?? normalizeInvoice(invoice);
  const buyerName = activeInvoice?.buyer?.name ?? activeInvoice?.buyer_name ?? "";
  const buyerGstin = activeInvoice?.buyer?.gstin ?? activeInvoice?.buyer_gstin ?? "";
  const buyerAddress = activeInvoice?.buyer?.address ?? activeInvoice?.buyer_address ?? "";
  const buyerState = activeInvoice?.buyer?.state ?? activeInvoice?.buyer_state ?? "";
  
  const items = activeInvoice?.items ?? activeInvoice?.line_items ?? [];
  const computedSummary = calculateSummary(activeInvoice);
  
  const displaySubtotal = isEditable
    ? computedSummary.subtotal
    : invoice?.subtotal ?? invoice?.gst_summary?.subtotal ?? 0;
  const displayTotal = isEditable
    ? computedSummary.grand_total
    : invoice?.grand_total ?? invoice?.gst_summary?.grand_total ?? 0;
  const cgstAmount = isEditable
    ? computedSummary.cgst_amount
    : invoice?.cgst_amount ?? invoice?.gst_summary?.cgst ?? 0;
  const sgstAmount = isEditable
    ? computedSummary.sgst_amount
    : invoice?.sgst_amount ?? invoice?.gst_summary?.sgst ?? 0;
  const igstAmount = isEditable
    ? computedSummary.igst_amount
    : invoice?.igst_amount ?? invoice?.gst_summary?.igst ?? 0;

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
            <div style={styles.row}>
              <span style={styles.label}>State:</span>
              {isEditable ? (
                <input
                  type="text"
                  value={buyerState}
                  onChange={(e) =>
                    updateInvoice((prev) => ({
                      ...prev,
                      buyer: {
                        ...(prev?.buyer ?? {}),
                        state: e.target.value,
                      },
                    }))
                  }
                  placeholder="Enter buyer state"
                  style={styles.input}
                />
              ) : (
                <span style={styles.value}>{buyerState || "-"}</span>
              )}
            </div>
          </div>
        </div>

        {/* Items Section */}
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Items</h3>
          <div style={styles.itemsContainer}>
            {items.map((item, index) => (
              <div key={item?.id ?? item?.sku ?? index} style={styles.itemCard}>
                <div style={styles.row}>
                  <span style={styles.label}>Description:</span>
                  {isEditable ? (
                    <input
                      type="text"
                      value={item?.description ?? ""}
                      onChange={(e) =>
                        updateInvoice((prev) => ({
                          ...prev,
                          items: prev.items.map((entry, entryIndex) =>
                            entryIndex === index
                              ? { ...entry, description: e.target.value }
                              : entry,
                          ),
                        }))
                      }
                      style={styles.input}
                    />
                  ) : (
                    <span style={styles.value}>{item?.description || "-"}</span>
                  )}
                </div>
                <div style={styles.row}>
                  <span style={styles.label}>HSN:</span>
                  {isEditable ? (
                    <input
                      type="text"
                      value={item?.hsn ?? item?.hsn_code ?? ""}
                      onChange={(e) => handleItemChange(index, "hsn", e.target.value)}
                      placeholder="Enter HSN"
                      style={styles.input}
                    />
                  ) : (
                    <span style={styles.value}>{item?.hsn ?? item?.hsn_code ?? "-"}</span>
                  )}
                </div>
                <div style={styles.row}>
                  <span style={styles.label}>Quantity:</span>
                  {isEditable ? (
                    <input
                      type="number"
                      min="0"
                      step="any"
                      value={item?.quantity ?? 0}
                      onChange={(e) =>
                        updateInvoice((prev) => ({
                          ...prev,
                          items: prev.items.map((entry, entryIndex) =>
                            entryIndex === index
                              ? { ...entry, quantity: toNumber(e.target.value) }
                              : entry,
                          ),
                        }))
                      }
                      style={styles.input}
                    />
                  ) : (
                    <span style={styles.value}>{item?.quantity}</span>
                  )}
                </div>
                {item?.unit_price !== undefined || item?.unitPrice !== undefined ? (
                  <div style={styles.row}>
                    <span style={styles.label}>Unit Price:</span>
                    {isEditable ? (
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={item?.unit_price ?? item?.unitPrice ?? 0}
                        onChange={(e) =>
                          updateInvoice((prev) => ({
                            ...prev,
                            items: prev.items.map((entry, entryIndex) =>
                              entryIndex === index
                                ? { ...entry, unit_price: toNumber(e.target.value) }
                                : entry,
                            ),
                          }))
                        }
                        style={styles.input}
                      />
                    ) : (
                      <span style={styles.value}>
                        ₹{(item?.unit_price ?? item?.unitPrice ?? 0).toFixed(2)}
                      </span>
                    )}
                  </div>
                ) : null}
                {item?.gst_rate !== undefined || item?.gstRate !== undefined ? (
                  <div style={styles.row}>
                    <span style={styles.label}>GST %:</span>
                    {isEditable ? (
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={item?.gst_rate ?? item?.gstRate ?? 0}
                        onChange={(e) =>
                          updateInvoice((prev) => ({
                            ...prev,
                            items: prev.items.map((entry, entryIndex) =>
                              entryIndex === index
                                ? { ...entry, gst_rate: Math.max(0, Math.round(toNumber(e.target.value))) }
                                : entry,
                            ),
                          }))
                        }
                        style={styles.input}
                      />
                    ) : (
                      <span style={styles.value}>
                        {(item?.gst_rate ?? item?.gstRate ?? 0)}%
                      </span>
                    )}
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
    textAlign: "right",
  },
  input: {
    width: "220px",
    maxWidth: "60%",
    borderRadius: "8px",
    border: "1px solid rgba(255, 255, 255, 0.16)",
    background: "rgba(255, 255, 255, 0.08)",
    color: "#f5f7fb",
    padding: "6px 10px",
    fontSize: "14px",
    outline: "none",
    textAlign: "right",
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
};

export default InvoicePreview;
