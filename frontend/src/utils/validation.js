import { authMessages } from '../data/auth';
const ID_PATTERN = /^[A-Za-z0-9_]+$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Each validator returns the message to show, or null when the value is fine. */

export function validateId(value) {
  const id = value.trim();
  if (!id) return authMessages.idRequired;
  if (id.length < 4) return authMessages.idTooShort;
  if (!ID_PATTERN.test(id)) return authMessages.idFormat;
  return null;
}
export function validateName(value) {
  return value.trim() ? null : authMessages.nameRequired;
}
export function validateEmail(value) {
  const email = value.trim();
  if (!email) return authMessages.emailRequired;
  if (!EMAIL_PATTERN.test(email)) return authMessages.emailFormat;
  return null;
}
export function validatePassword(value) {
  if (!value) return authMessages.passwordRequired;
  if (value.length < 8) return authMessages.passwordTooShort;
  return null;
}
export function validateConfirm(password, confirm) {
  return confirm === password ? null : authMessages.confirmMismatch;
}
