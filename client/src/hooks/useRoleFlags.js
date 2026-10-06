// Derives the set of boolean role flags used throughout the dashboard
// pages. Previously defined identically in both Dashboard.jsx (Purchase
// Orders) and InvoiceDashboard.jsx (Invoices) — seven lines copy-pasted
// between the two.
export function useRoleFlags(user) {
  const role = String(user?.role || '').toUpperCase()

  return {
    role,
    isCompanyAdmin: role === 'COMPANY_ADMIN',
    isUser: role === 'USER',
    isMasterAdmin: role === 'MASTER_ADMIN',
    isFinancial: role === 'FINANCIAL' || role === 'FINANCE',
    isOperations: role === 'OPERATION' || role === 'OPERATIONS',
    isLegal: role === 'LEGAL',
    isInternal: ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL'].includes(role),
  }
}
