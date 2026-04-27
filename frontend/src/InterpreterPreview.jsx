import "./InterpreterPreview.css";

const asNumber = (value) => {
	const num = Number(value);
	return Number.isFinite(num) ? num : 0;
};

const formatCurrency = (value) => {
	const amount = asNumber(value);
	return amount.toLocaleString("en-IN", {
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	});
};

const displayValue = (value) => {
	if (value === null || value === undefined || value === "") {
		return "-";
	}
	return String(value);
};

function MessageCard({ message }) {
	return (
		<section className="ip-card">
			<h3 className="ip-section-title">AI Understanding</h3>
			<p className="ip-message-text">{displayValue(message)}</p>
		</section>
	);
}

function CustomerCard({ customer }) {
	const safeCustomer = customer || {};

	return (
		<section className="ip-card">
			<h3 className="ip-section-title">Customer</h3>
			<div className="ip-grid">
				<div className="ip-grid-item">
					<span className="ip-label">Name</span>
					<span className="ip-value">{displayValue(safeCustomer.name)}</span>
				</div>
				<div className="ip-grid-item">
					<span className="ip-label">Phone</span>
					<span className="ip-value">{displayValue(safeCustomer.phone)}</span>
				</div>
				<div className="ip-grid-item">
					<span className="ip-label">Type</span>
					<span className="ip-value">{displayValue(safeCustomer.type)}</span>
				</div>
			</div>
		</section>
	);
}

function ItemsTable({ items }) {
	const safeItems = Array.isArray(items) ? items : [];

	return (
		<section className="ip-card">
			<h3 className="ip-section-title">Items</h3>
			{safeItems.length === 0 ? (
				<p className="ip-empty-text">No items found.</p>
			) : (
				<div className="ip-table-wrapper">
					<table className="ip-table">
						<thead>
							<tr>
								<th className="ip-th">Name</th>
								<th className="ip-th ip-th-right">Qty</th>
								<th className="ip-th ip-th-right">Price</th>
								<th className="ip-th ip-th-right">Total</th>
							</tr>
						</thead>
						<tbody>
							{safeItems.map((item, index) => {
								const quantity = asNumber(item?.quantity);
								const price = asNumber(item?.price);
								const lineTotal = quantity * price;

								return (
									<tr key={`${item?.name || "item"}-${index}`}>
										<td className="ip-td">{displayValue(item?.name)}</td>
										<td className="ip-td ip-td-right">{displayValue(item?.quantity)}</td>
										<td className="ip-td ip-td-right">{formatCurrency(price)}</td>
										<td className="ip-td ip-td-right">{formatCurrency(lineTotal)}</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			)}
		</section>
	);
}

function TotalsCard({ gst, total }) {
	return (
		<section className="ip-card">
			<h3 className="ip-section-title">Totals</h3>
			<div className="ip-row">
				<span className="ip-label">GST</span>
				<span className="ip-value">
					{gst === null || gst === undefined || gst === "" ? "-" : `${gst}%`}
				</span>
			</div>
			<div className="ip-row">
				<span className="ip-label">Invoice Total</span>
				<span className="ip-value">{formatCurrency(total)}</span>
			</div>
		</section>
	);
}

function WarningsCard({ warnings }) {
	const safeWarnings = Array.isArray(warnings) ? warnings.filter(Boolean) : [];

	return (
		<section className="ip-card">
			<h3 className="ip-section-title">Warnings</h3>
			{safeWarnings.length === 0 ? (
				<p className="ip-empty-text">No warnings.</p>
			) : (
				<ul className="ip-warning-list">
					{safeWarnings.map((warning, index) => (
						<li key={`${warning}-${index}`} className="ip-warning-item">
							{warning}
						</li>
					))}
				</ul>
			)}
		</section>
	);
}

function ActionsBar({ actions, onCreateInvoice, onAddCustomer }) {
	const safeActions = Array.isArray(actions) ? actions : [];
	const canCreateInvoice = safeActions.includes("create_invoice");
	const canAddCustomer = safeActions.includes("add_customer");

	return (
		<section className="ip-card">
			<h3 className="ip-section-title">Actions</h3>
			<div className="ip-actions-row">
				<button
					type="button"
					className={canCreateInvoice ? "ip-btn ip-btn-primary" : "ip-btn ip-btn-disabled"}
					onClick={onCreateInvoice}
					disabled={!canCreateInvoice}
				>
					Create Invoice
				</button>
				<button
					type="button"
					className={canAddCustomer ? "ip-btn ip-btn-secondary" : "ip-btn ip-btn-disabled"}
					onClick={onAddCustomer}
					disabled={!canAddCustomer}
				>
					Add Customer
				</button>
			</div>
		</section>
	);
}

export default function InterpreterPreview({
	data,
	onCreateInvoice = () => {},
	onAddCustomer = () => {},
}) {
	const payload = data || {};
	const customer = payload.customer || {};
	const invoice = payload.invoice || {};
	const confidence = payload.confidence;

	return (
		<div className="ip-container">
			<MessageCard message={payload.message} />
			<section className="ip-card">
				<h3 className="ip-section-title">Confidence</h3>
				<p className="ip-message-text">{displayValue(confidence)}</p>
			</section>
			<CustomerCard customer={customer} />
			<ItemsTable items={invoice.items} />
			<TotalsCard gst={invoice.gst} total={invoice.total} />
			<WarningsCard warnings={payload.warnings} />
			<ActionsBar
				actions={payload.actions}
				onCreateInvoice={onCreateInvoice}
				onAddCustomer={onAddCustomer}
			/>
		</div>
	);
}
