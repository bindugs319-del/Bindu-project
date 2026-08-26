import PropTypes from 'prop-types'
import { salesInvoices } from '../../services/api/apiClient'
import GenericCSVImportModal from '../shared/GenericCSVImportModal'
import { formatDateToISO, parseAmount, looksLikePercent } from '../../utils/csvImportHelpers'

const FIELD_ALIASES = {
  invoice_number: ["Invoice #", "Invoice Number", "Invoice No", "Bill No", "Reference"],
  invoice_date: ["Invoice Date", "Date", "Bill Date"],
  payment_due_date: ["Due Date", "Payment Due Date", "Due", "Payment Due"],
  counterparty_name: ["Counterparty", "Counterparty Name", "Customer", "Customer Name", "Client", "Bill To"],
  counterparty_gstin: ["GSTIN", "Counterparty GSTIN", "GSTIN/UIN", "Tax ID", "GST No"],
  counterparty_email: ["Email", "Counterparty Email", "Customer Email", "Contact Email"],
  counterparty_phone: ["Phone", "Mobile", "Counterparty Phone", "Contact"],
  subtotal: ["Subtotal", "Sub Total", "Taxable Amount"],
  tax_rate_percent: ["Tax %", "Tax Rate", "GST %", "GST Rate", "Tax Percent", "GST Percent"],
  tax_amount: ["Tax Amount", "GST Amount", "Tax"],
  total: ["Total", "Amount", "Grand Total", "Invoice Amount"],
  status: ["Status"],
}

const FIELD_LABELS = {
  invoice_number: 'Invoice Number',
  invoice_date: 'Invoice Date',
  payment_due_date: 'Payment Due Date',
  counterparty_name: 'Counterparty Name',
  counterparty_gstin: 'GSTIN',
  counterparty_email: 'Email',
  counterparty_phone: 'Phone',
  subtotal: 'Subtotal',
  tax_rate_percent: 'Tax Rate (%)',
  tax_amount: 'Tax Amount (₹)',
  total: 'Total',
  status: 'Status',
}

const REQUIRED_FIELDS = ['invoice_date', 'payment_due_date', 'counterparty_name']
const VALID_STATUSES = ['Draft', 'Pending Operations Review', 'Pending Master Admin Approval', 'Approved', 'Paid']

function transformRow(row, mapping) {
  const rawTotalStr = mapping.total ? String(row[mapping.total] ?? '').trim() : ''
  const rawSubtotalStr = mapping.subtotal ? String(row[mapping.subtotal] ?? '').trim() : ''
  const rawTaxAmountStr = mapping.tax_amount ? String(row[mapping.tax_amount] ?? '').trim() : ''
  const rawTaxRateStr = mapping.tax_rate_percent ? String(row[mapping.tax_rate_percent] ?? '').trim() : ''

  let total = rawTotalStr ? parseAmount(rawTotalStr) : 0
  let subtotal = rawSubtotalStr ? parseAmount(rawSubtotalStr) : 0
  let taxAmount = rawTaxAmountStr ? parseAmount(rawTaxAmountStr) : 0

  // A rate applies if it's explicitly mapped to "Tax Rate (%)", or if
  // whatever got mapped to "Tax Amount" actually contains a % sign
  // (e.g. someone's "Tax" column has "18%" instead of a rupee value).
  const hasExplicitRate = !!rawTaxRateStr
  const taxIsActuallyRate = !hasExplicitRate && looksLikePercent(rawTaxAmountStr)
  const rate = hasExplicitRate ? parseAmount(rawTaxRateStr) : (taxIsActuallyRate ? parseAmount(rawTaxAmountStr) : null)

  if (rate !== null) {
    // We have a percentage rate -- derive amounts from whichever of
    // Subtotal / Total was actually filled in.
    if (rawSubtotalStr) {
      taxAmount = subtotal * (rate / 100)
      total = subtotal + taxAmount
    } else if (rawTotalStr) {
      subtotal = total / (1 + rate / 100)
      taxAmount = total - subtotal
    } else {
      taxAmount = 0
    }
  } else {
    // Flat currency tax amount -- fall back to auto-filling whichever
    // of Total / Subtotal is missing, using the other plus Tax Amount.
    if (!rawTotalStr && rawSubtotalStr) {
      total = subtotal + taxAmount
    } else if (!rawSubtotalStr && rawTotalStr) {
      subtotal = Math.max(total - taxAmount, 0)
    } else if (!rawTotalStr && !rawSubtotalStr) {
      total = 0
      subtotal = 0
    }
  }

  const rawStatus = String(row[mapping.status] || 'Draft').trim()
  const status = VALID_STATUSES.find(s => s.toLowerCase() === rawStatus.toLowerCase()) || 'Draft'

  return {
    invoice_number: String(row[mapping.invoice_number] || '').trim() || undefined,
    invoice_date: formatDateToISO(row[mapping.invoice_date]) || new Date().toISOString().split('T')[0],
    payment_due_date: formatDateToISO(row[mapping.payment_due_date]) || new Date().toISOString().split('T')[0],
    counterparty_name: String(row[mapping.counterparty_name] || '').trim(),
    counterparty_gstin: String(row[mapping.counterparty_gstin] || '').trim() || undefined,
    counterparty_email: String(row[mapping.counterparty_email] || '').trim() || undefined,
    counterparty_phone: String(row[mapping.counterparty_phone] || '').trim() || undefined,
    subtotal: Math.round(subtotal * 100) / 100,
    tax_amount: Math.round(taxAmount * 100) / 100,
    total: Math.round(total * 100) / 100,
    balance_due: total,
    status,
    items: [],
  }
}

const INVOICE_CONFIG = {
  modalTitle: 'Import Invoices',
  bannerTitle: 'Bulk Import',
  bannerBullets: [
    'Upload your file to automatically map columns',
    'Review and confirm before final import',
    'Required: Counterparty Name, Invoice Date, Payment Due Date',
  ],
  fileInputId: 'invoice-import-file',
  fieldColumnLabel: 'Invoice',
  fieldLabels: FIELD_LABELS,
  requiredFields: REQUIRED_FIELDS,
  unmappedAlwaysRed: false,
  proTip: 'Ensure Counterparty Name, Invoice Date, and Payment Due Date are correctly mapped for accurate processing. If your tax is a percentage (e.g. 18% GST), map it to "Tax Rate (%)" instead of "Tax Amount" — the rupee tax and Total will be calculated automatically from your Subtotal.',
  hasImportTypeSelector: false,
  mappings: FIELD_ALIASES,
  transformRow,
  rowFilter: (r) => r.counterparty_name,
  createFn: salesInvoices.create,
  skippedFilePrefix: 'skipped_invoices',
}

export default function InvoiceCSVImportModal({ onClose, onImportComplete, initialFile }) {
  return (
    <GenericCSVImportModal
      onClose={onClose}
      onImportComplete={onImportComplete}
      initialFile={initialFile}
      config={INVOICE_CONFIG}
    />
  )
}

InvoiceCSVImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func.isRequired,
  initialFile: PropTypes.object,
}
