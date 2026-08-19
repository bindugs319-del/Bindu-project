// Frontend stubs for OTP flows. Replace with real API integration.

export async function sendOtp({ phone, reason }) {
  return { ok: true, message: 'OTP sent (stub)' }
}

export async function verifyOtp({ phone, code }) {
  return { ok: code === '123456', message: 'OTP verified (stub accepts 123456)' }
}
