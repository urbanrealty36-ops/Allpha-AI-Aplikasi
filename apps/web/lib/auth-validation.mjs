/** Validate a user-entered email before submitting Supabase Auth credentials. */
export function isValidEmail(value) {
  return /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(value.trim());
}
