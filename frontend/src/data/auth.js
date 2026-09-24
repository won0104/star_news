/** Copy for the auth screens — Figma V6 / Auth / 로그인 (627:3) and 회원가입 (627:34). */

export const authBrand = {
  name: '별빛 뉴스',
  tagline: '당신만의 뉴스 다락방'
};

/**
 * 로그인·회원가입이 놓인 방 — data/home 의 `rooms` 와 같은 방이고, 현관과 기사 상세도 같은
 * 장을 쓴다.
 *
 * <PhotoBackdrop> 의 scene 모양을 따른다. `src` 를 비워 두면 <PhotoBackdrop> 이 비율에 맞는
 * 장을 골라 깐다. 예전에는 16:9 한 장을 cover 로 잘라 썼는데, 세로로 긴 창에서는 창과 소파가
 * 잘려 나가 방이 벽만 남았다.
 *
 * `loop` 는 없다. 이 방의 움직이는 클립이 없고, 다른 방의 클립을 붙이면 전혀 다른 방으로
 * 넘어가는 컷이 된다.
 *
 * 클립보드는 CSS 만 쓰므로 여기 두지 않는다 — 자리와 조각 기하는 Auth.module.css 에 있다.
 */
export const authScene = {
  id: 'auth',
  loop: null
};
export const loginCopy = {
  title: '로그인',
  subtitle: '나만의 뉴스 다락방으로 다시 돌아오세요',
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
  subtitle: '별빛 뉴스에서 나만의 뉴스 기록을 만들어 보세요',
  id: {
    label: '아이디',
    placeholder: '사용할 아이디를 입력하세요'
  },
  duplicateCheck: '중복확인',
  nickname: {
    label: '닉네임',
    placeholder: '2~50자로 입력하세요'
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
  idFormat: '아이디는 영문 소문자, 숫자, 밑줄(_)만 사용할 수 있습니다.',
  idTooLong: '아이디는 50자 이하여야 합니다.',
  idChecking: '확인 중…',
  idAvailable: '사용 가능한 아이디입니다.',
  idTaken: '이미 사용 중인 아이디입니다.',
  idUnchecked: '아이디 중복확인을 해 주세요.',
  nicknameRequired: '닉네임을 입력해 주세요.',
  nicknameTooShort: '닉네임은 2자 이상이어야 합니다.',
  nicknameTooLong: '닉네임은 50자 이하여야 합니다.',
  emailRequired: '이메일을 입력해 주세요.',
  emailFormat: '올바른 이메일 형식이 아닙니다.',
  passwordRequired: '비밀번호를 입력해 주세요.',
  passwordTooShort: '비밀번호는 8자 이상이어야 합니다.',
  passwordTooLong: '비밀번호는 20자 이하여야 합니다.',
  confirmMismatch: '비밀번호가 일치하지 않습니다.',
  termsRequired: '약관에 동의해야 가입할 수 있습니다.',
  loginFailed: '아이디 또는 비밀번호를 확인해 주세요.',
  loginDeleted: '탈퇴한 계정입니다.',
  signupFailed: '가입에 실패했습니다. 잠시 후 다시 시도해 주세요.',
  networkFailed: '서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
};
