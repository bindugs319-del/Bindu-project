import PropTypes from 'prop-types'
import { purchaseOrders } from '../../services/api/apiClient'
import GenericCSVImportModal from '../shared/GenericCSVImportModal'
import { formatDateToISO, parseAmount } from '../../utils/csvImportHelpers'

const IMPORT_TYPES = {
  DEFAULT: 'DEFAULT',
  ZOHO: 'ZOHO',
  TALLY: 'TALLY'
}

const MAPPINGS_BY_TYPE = {
  [IMPORT_TYPES.DEFAULT]: {
    po_number: ["PO #", "PO Number", "Voucher No.", "Invoice No", "Bill No", "Purchase Order#", "Reference"],
    vendor_name: ["Vendor", "Vendor Name", "Particulars", "Party Name", "Supplier", "Ledger"],
    gstin: ["GSTIN", "GSTIN/UIN", "Tax ID", "GST No", "Registration"],
    amount: ["Amount", "Gross Total", "Net Amount", "Total", "Value"],
    due_date: ["Due", "Date", "Bill Date", "Invoice Date", "Due Date", "Voucher Date"],
    email: ["Email", "Vendor Email", "Mail", "Contact Email"],
    mobile: ["Mobile", "Phone", "Contact", "Number"],
    payment_window: ["Window", "Days", "Terms", "Credit Period", "Payment Days"]
  },
  [IMPORT_TYPES.ZOHO]: {
    po_number: ["PO Number"],
    vendor_name: ["Vendor Name"],
    due_date: ["PO Date"],
    item_name: ["Item Name"],
    quantity: ["Quantity"],
    rate: ["Rate"],
    amount: ["Amount"]
  },
  [IMPORT_TYPES.TALLY]: {
    po_number: ["Voucher Number", "PO Number"],
    vendor_name: ["Party Name"],
    due_date: ["Date"],
    item_name: ["Stock Item"],
    quantity: ["Billed Qty"],
    rate: ["Rate"],
    amount: ["Amount"]
  }
}

const FIELD_LABELS = {
  po_number: 'PO Number',
  vendor_name: 'Vendor Name',
  gstin: 'GSTIN',
  amount: 'Amount',
  due_date: 'Due Date',
  email: 'Email',
  mobile: 'Mobile',
  payment_window: 'Payment Window'
}

function transformRow(row, mapping) {
  const notesParts = []
  if (mapping.item_name && row[mapping.item_name]) notesParts.push(`Item: ${row[mapping.item_name]}`)
  if (mapping.quantity && row[mapping.quantity]) notesParts.push(`Qty: ${row[mapping.quantity]}`)
  if (mapping.rate && row[mapping.rate]) notesParts.push(`Rate: ${row[mapping.rate]}`)

  return {
    po_number: String(row[mapping.po_number] || '').trim(),
    vendor: String(row[mapping.vendor_name] || '').trim(),
    gstin: String(row[mapping.gstin] || 'PENDING').trim().toUpperCase(),
    amount: parseAmount(row[mapping.amount]),
    due_date: formatDateToISO(row[mapping.due_date]) || new Date().toISOString().split('T')[0],
    vendor_email: String(row[mapping.email] || '').trim(),
    vendor_phone: String(row[mapping.mobile] || '').replace(/[\s-]/g, ''),
    payment_window_days: parseInt(row[mapping.payment_window]) || 50,
    status: 'Open',
    notes: notesParts.join(' | ')
  }
}

const PO_CONFIG = {
  modalTitle: 'Import Purchase Orders',
  bannerTitle: 'Structured Import',
  bannerBullets: [
    'Select your Excel format (Default, Zoho, or Tally)',
    'Upload your file to automatically map columns',
    'Review and confirm before final import',
  ],
  fileInputId: 'import-file',
  fieldColumnLabel: 'PO',
  fieldLabels: FIELD_LABELS,
  requiredFields: ['po_number', 'vendor_name', 'amount'],
  unmappedAlwaysRed: true,
  proTip: 'Ensure PO Number, Vendor Name, and Amount are correctly mapped for accurate processing.',
  hasImportTypeSelector: true,
  importTypes: Object.values(IMPORT_TYPES),
  mappingsByType: MAPPINGS_BY_TYPE,
  transformRow,
  rowFilter: (r) => r.vendor || r.po_number,
  createFn: purchaseOrders.create,
  skippedFilePrefix: 'skipped_pos',
}

export default function CSVImportModal({ onClose, onImportComplete, initialFile }) {
  return (
    <GenericCSVImportModal
      onClose={onClose}
      onImportComplete={onImportComplete}
      initialFile={initialFile}
      config={PO_CONFIG}
    />
  )
}

CSVImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func.isRequired,
  initialFile: PropTypes.object,
}
