import PropTypes from 'prop-types'
import { purchaseOrders } from '../../services/api/apiClient'
import DocumentImportModal from '../shared/DocumentImportModal'

const PO_CONFIG = {
  title: 'Import PO from PDF',
  subtitle: 'Upload a Purchase Order PDF — we\u2019ll read it and fill in the fields for you to confirm.',
  fieldLabels: {
    po_number: 'PO Number',
    vendor: 'Vendor Name',
    gstin: 'Vendor GSTIN',
    vendor_email: 'Vendor Email',
    vendor_phone: 'Vendor Mobile',
    amount: 'Amount',
    due_date: 'Due Date',
    payment_window_days: 'Payment Window (Days)',
  },
  dateFields: ['due_date'],
  numberFields: ['amount', 'payment_window_days'],
  requiredFields: ['vendor', 'po_number'],
  scanFn: purchaseOrders.scanPdf,
  importFn: purchaseOrders.importPdf,
  entityLabel: 'PO',
  entityNumberField: 'po_number',
}

export default function PDFImportModal({ onClose, onImportComplete, initialFile }) {
  return (
    <DocumentImportModal
      onClose={onClose}
      onImportComplete={onImportComplete}
      initialFile={initialFile}
      config={PO_CONFIG}
    />
  )
}

PDFImportModal.propTypes = {
  onClose: PropTypes.func.isRequired,
  onImportComplete: PropTypes.func,
  initialFile: PropTypes.object,
}
