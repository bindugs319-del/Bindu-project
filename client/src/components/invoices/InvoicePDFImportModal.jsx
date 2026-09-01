import PropTypes from 'prop-types'
import { salesInvoices } from '../../services/api/apiClient'
import DocumentImportModal from '../shared/DocumentImportModal'

const INVOICE_CONFIG = {
  title: 'Import Invoice from PDF',
  subtitle: 'Upload a Tax Invoice PDF — we\u2019ll read it and fill in the fields for you to confirm.',
  fieldLabels: {
    invoice_number: 'Invoice Number',
    counterparty_name: 'Counterparty Name',
    counterparty_gstin: 'GSTIN',
    counterparty_email: 'Email',
    counterparty_phone: 'Phone',
    subtotal: 'Subtotal',
    tax_amount: 'Tax Amount',
    total: 'Total',
    currency: 'Currency (e.g. INR, USD)',
    invoice_date: 'Invoice Date',
    payment_due_date: 'Payment Due Date',
  },
  dateFields: ['invoice_date', 'payment_due_date'],
  numberFields: ['subtotal', 'tax_amount', 'total'],
  requiredFields: ['counterparty_name', 'invoice_number'],
  scanFn: salesInvoices.scanPdf,
  importFn: salesInvoices.importPdf,
  entityLabel: 'Invoice',
  entityNumberField: 'invoice_number',
  extraNote: 'Note: line items aren\u2019t read from the PDF. A new invoice is created with no items; an existing invoice keeps its current items.',
}

export default function InvoicePDFImportModal({ onClose, onImportComplete, initialFile }) {
  return (
    <DocumentImportModal
      onClose={onClose}
      onImportComplete={onImportComplete}
      initialFile={initialFile}
      config={INVOICE_CONFIG}
    />
  )
}

InvoicePDFImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func,
  initialFile: PropTypes.object,
}
