import { authMessages } from '../data/auth';
// 서버 계약: 영문 소문자·숫자·밑줄 4~50자. 대문자를 여기서 통과시키면 가입 요청이
// 400으로 되돌아오므로, 규칙은 서버 쪽에 맞춘다.
const ID_PATTERN = /^[a-z0-9_]+$/;
const ID_MAX = 50;
const NICKNAME_MIN = 2;
const NICKNAME_MAX = 50;
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 20;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Each validator returns the message to show, or null when the value is fine. */

export function validateId(value) {
  const id = value.trim();
  if (!id) return authMessages.idRequired;
  if (id.length < 4) return authMessages.idTooShort;
  if (id.length > ID_MAX) return authMessages.idTooLong;
  if (!ID_PATTERN.test(id)) return authMessages.idFormat;
  return null;
}
export function validateNickname(value) {
  const nickname = value.trim();
  if (!nickname) return authMessages.nicknameRequired;
  if (nickname.length < NICKNAME_MIN) return authMessages.nicknameTooShort;
  if (nickname.length > NICKNAME_MAX) return authMessages.nicknameTooLong;
  return null;
}
export function validateEmail(value) {
  const email = value.trim();
  if (!email) return authMessages.emailRequired;
  if (!EMAIL_PATTERN.test(email)) return authMessages.emailFormat;
  return null;
}
export function validatePassword(value) {
  if (!value) return authMessages.passwordRequired;
  if (value.length < PASSWORD_MIN) return authMessages.passwordTooShort;
  if (value.length > PASSWORD_MAX) return authMessages.passwordTooLong;
  return null;
}
export function validateConfirm(password, confirm) {
  return confirm === password ? null : authMessages.confirmMismatch;
}
