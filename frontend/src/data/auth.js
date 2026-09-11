/** Copy for the auth screens — Figma V6 / Auth / 로그인 (627:3) and 회원가입 (627:34). */

export const authBrand = {
  name: '별빛 뉴스',
  tagline: '당신만의 뉴스 우주'
};
export const loginCopy = {
  title: '로그인',
  subtitle: '나만의 뉴스 우주로 다시 돌아오세요',
  id: {
    label: '아이디',
    placeholder: '아이디를 입력하세요'
  },
  password: {
    label: '비밀번호',
    placeholder: '8자 이상 입력하세요'
  },
  submit: '로그인',
  prompt: '아직 계정이 없으신가요?',
  promptAction: '회원가입'
};
export const signupCopy = {
  title: '회원가입',
  subtitle: '별빛 뉴스에서 나만의 뉴스 우주를 시작하세요',
  id: {
    label: '아이디',
    placeholder: '사용할 아이디를 입력하세요'
  },
  duplicateCheck: '중복확인',
  name: {
    label: '이름',
    placeholder: '이름을 입력하세요'
  },
  email: {
    label: '이메일',
    placeholder: 'you@example.com'
  },
  password: {
    label: '비밀번호',
    placeholder: '8자 이상 입력하세요'
  },
  confirm: {
    label: '비밀번호 확인',
    placeholder: '비밀번호를 다시 입력하세요'
  },
  terms: '이용약관 및 개인정보처리방침에 동의합니다',
  submit: '회원가입',
  prompt: '이미 계정이 있으신가요?',
  promptAction: '로그인'
};

/** Validation and status messages. Only `idAvailable` appears in the Figma; the rest follow its tone. */
export const authMessages = {
  idRequired: '아이디를 입력해 주세요.',
  idTooShort: '아이디는 4자 이상이어야 합니다.',
  idFormat: '아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.',
  idChecking: '확인 중…',
  idAvailable: '사용 가능한 아이디입니다.',
  idTaken: '이미 사용 중인 아이디입니다.',
  idUnchecked: '아이디 중복확인을 해 주세요.',
  nameRequired: '이름을 입력해 주세요.',
  emailRequired: '이메일을 입력해 주세요.',
  emailFormat: '올바른 이메일 형식이 아닙니다.',
  passwordRequired: '비밀번호를 입력해 주세요.',
  passwordTooShort: '비밀번호는 8자 이상이어야 합니다.',
  confirmMismatch: '비밀번호가 일치하지 않습니다.',
  termsRequired: '약관에 동의해야 가입할 수 있습니다.',
  loginFailed: '아이디 또는 비밀번호를 확인해 주세요.',
  signupFailed: '가입에 실패했습니다. 잠시 후 다시 시도해 주세요.'
};
