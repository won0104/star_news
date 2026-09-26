import { Fragment, useLayoutEffect, useRef, useState } from 'react';
import { authActions, brand, navItems, navSectionOf } from '../../data/home';
import { useHasNavRail } from '../../hooks/useHasNavRail';
import { useSession } from '../../store/session';
import { NodeSearch } from './NodeSearch';
import { UserMenu } from './UserMenu';
import styles from './TopBar.module.css';

/**
 * Site chrome over the room photo: brand, section nav, and the right-hand end, which is
 * the sign-in and sign-up entry points until someone signs in and the account mark and
 * its menu take their place.
 *
 * The nav is now the whole of the site's navigation — the left menu board it used to
 * share the job with is gone, and the four destinations that were nested inside it (two
 * board entries, each with a two-tab strip) are flat here.
 *
 * The hairlines between buttons are their own elements rather than a border or a
 * `::before` on the button, because the active button is a filled dark pill: a rule
 * drawn on the button would sit inside that pill, and a border would ride the pill's
 * rounded edge. Free-standing spans stay clear of it, and being decorative they are
 * `aria-hidden` — the nav's own list semantics say where one item ends.
 *
 * `nightGlass` keeps the same translucent chrome over a dark scene while letting more
 * of that scene through than the sunlit-room default.
 *
 * `onAuth` is only asked for while nobody is signed in. The account menu needs nothing
 * from here — its entries open the settings overlay and end the session themselves.
 *
 * `onBrand` is where the mark leads, and it is separate from `onSelect` because the mark
 * is not a fifth destination: from inside the app it leaves for the front of the site.
 * Without it the mark falls back to opening the first destination, which is what the
 * screens that are already at the front want.
 *
 * `search` 를 켜면 검색창도 이 chrome 의 일부가 된다. 세로 레일에서는 이름과 첫 목적지
 * 사이에 늘 자리를 차지하고, 가로 상단바에서는 아이콘 하나로 줄어 눌렀을 때만 예전 그
 * 자리에 떠오른다 — 상단바는 폭이 좁아 검색창까지 늘 펼쳐 둘 자리가 없다.
 */
/*
 * 책갈피가 바 뒤로 물리는 깊이. 이만큼은 바에 가려 보이지 않고, 나머지만 아래로 나온다 —
 * 책에 끼운 책갈피처럼. TopBar.module.css 의 .navSub 가 같은 값을 위쪽 여백으로 갖는다.
 */
const TAB_TUCK = 18;

export function TopBar({
  activeId,
  onSelect,
  onBrand,
  onAuth,
  onIntent,
  nightGlass = false,
  search = false,
  onSearchSelect,
}) {
  const account = useSession();
  const navRef = useRef(null);
  const barRef = useRef(null);
  const sectionRef = useRef(null);
  const rail = useHasNavRail();
  const section = navSectionOf(activeId);
  /*
   * 책갈피가 설 자리. 갈래 단추의 왼쪽 변과, 바 아래로 내려올 높이다.
   *
   * 정해진 값으로는 따라갈 수 없다 — 갈래마다 가로 위치가 다르고, 좁은 폭에서 <nav> 가 옆으로
   * 스크롤되면 그 사이에도 움직인다. 세로는 바의 실제 아래 변에서 TUCK 만큼 끌어올린 값이라,
   * 바 높이를 CSS 와 여기 두 군데에 적지 않아도 된다.
   */
  const [tab, setTab] = useState({ left: 0, top: 0 });
  // 레일에서는 늘 펼쳐져 있으므로 이 값은 상단바일 때만 읽는다.
  const [searchOpen, setSearchOpen] = useState(false);

  useLayoutEffect(() => {
    if (rail) return undefined;
    const button = sectionRef.current;
    const bar = barRef.current;
    const nav = navRef.current;
    if (!button || !bar) return undefined;

    const place = () => {
      const b = button.getBoundingClientRect();
      const r = bar.getBoundingClientRect();
      setTab({ left: Math.round(b.left), top: Math.round(r.bottom - TAB_TUCK) });
    };
    place();

    // 바가 줄어들면 단추가 밀리고, 목록이 옆으로 스크롤되면 단추가 지나간다. 둘 다 본다.
    const observer = new ResizeObserver(place);
    observer.observe(bar);
    nav?.addEventListener('scroll', place, { passive: true });
    return () => {
      observer.disconnect();
      nav?.removeEventListener('scroll', place);
    };
  }, [rail, activeId]);

  useLayoutEffect(() => {
    // A direct link or narrower window can hide the selected tab beyond the scroll edge.
    const showActive = () => {
      navRef.current?.querySelector('[aria-current="page"]')?.scrollIntoView({
        block: 'nearest',
        inline: 'nearest',
      });
    };

    showActive();
    window.addEventListener('resize', showActive);
    return () => window.removeEventListener('resize', showActive);
  }, [activeId]);

  /*
   * 지금 있는 갈래의 잎. 레일에서는 갈래 안에 들어가 아래로 이어지고, 상단바에서는 <nav> 바깥
   * 바의 자식으로 서서 말풍선이 된다 — <nav> 가 옆으로 스크롤되느라 그 안의 것을 잘라내서다.
   * 만드는 것은 한 번뿐이고 놓는 자리만 다르다.
   */
  const leaves = section?.children?.length ? (
    <span className={styles.navSub} style={rail ? undefined : tab}>
      {section.children.map((child) => (
        <button
          key={child.id}
          type="button"
          className={`${styles.navSubItem} ${child.id === activeId ? styles.navSubItemActive : ''}`}
          aria-current={child.id === activeId ? 'page' : undefined}
          onPointerEnter={() => onIntent?.(child.id)}
          onFocus={() => onIntent?.(child.id)}
          onClick={() => onSelect(child.id)}
        >
          {child.label}
        </button>
      ))}
    </span>
  ) : null;

  return (
    <>
      <header ref={barRef} className={`${styles.bar} ${nightGlass ? styles.nightGlass : ''}`}>
      <button
        type="button"
        className={styles.brand}
        onClick={onBrand ?? (() => onSelect(navItems[0].id))}
      >
        <span className={styles.wordmark} aria-hidden />
        <span className={styles.srOnly}>{brand.name}</span>
      </button>

      {/* 레일에서는 이름과 목적지 사이의 한 칸, 상단바에서는 자리를 차지하지 않는
          껍데기다(display: contents) — 좁은 폭의 상단바는 grid 라 빈 칸이 늘면 배치가 어긋난다. */}
      {search && (rail || searchOpen) && (
        <div className={styles.searchSlot}>
          <NodeSearch
            night={nightGlass}
            placement={rail ? 'rail' : 'floating'}
            takeFocus={!rail}
            onSelect={onSearchSelect}
          />
        </div>
      )}

      {/*
        갈래는 늘 셋이고, 그 아래는 지금 있는 갈래 것만 펼친다 — 다른 갈래의 잎까지 늘 보이면
        다시 다섯 줄이 되어 갈래로 묶은 뜻이 없어진다. 잎에 들어와 있어도 갈래는 켜진 채로 둔다:
        오늘의 트렌드에 서 있는 동안 탐색이 꺼지면 내가 어디 있는지 읽히지 않는다.
      */}
      <nav ref={navRef} className={styles.nav}>
        {navItems.map((item, index) => (
          <Fragment key={item.id}>
            {index > 0 && <span className={styles.navRule} aria-hidden />}
            <span className={styles.navSection}>
              {/*
                누르기 전에 한 번 알린다 — 포인터가 올라오거나 탭 이동으로 초점이 닿는 순간이
                목적지를 고른 순간에 가장 가깝다. 무엇을 미리 할지는 받는 쪽이 정한다.
              */}
              <button
                ref={item.id === section?.id ? sectionRef : undefined}
                type="button"
                className={`${styles.navItem} ${item.id === section?.id ? styles.navItemActive : ''}`}
                aria-current={item.id === activeId ? 'page' : undefined}
                onPointerEnter={() => onIntent?.(item.id)}
                onFocus={() => onIntent?.(item.id)}
                onClick={() => onSelect(item.id)}
              >
                {item.label}
              </button>

              {rail && item.id === section?.id && leaves}
            </span>
          </Fragment>
        ))}
      </nav>

      <div className={styles.spacer} />

      {search && !rail && (
        <button
          type="button"
          className={styles.searchToggle}
          aria-expanded={searchOpen}
          aria-label={searchOpen ? '검색 닫기' : '검색 열기'}
          onClick={() => setSearchOpen((open) => !open)}
        >
          <span aria-hidden>⌕</span>
        </button>
      )}

      <div className={styles.auth}>
        {account ? (
          <UserMenu account={account} />
        ) : (
          <>
            <button type="button" className={styles.signIn} onClick={() => onAuth('login')}>
              {authActions.signIn}
            </button>
            <button type="button" className={styles.signUp} onClick={() => onAuth('signup')}>
              {authActions.signUp}
            </button>
          </>
        )}
      </div>
      </header>

      {/*
        책갈피는 바의 형제다. 자식이면 부모 배경이 먼저 칠해지고 그 위에 그려져, z-index 를
        어떻게 주어도 뒤로 물릴 수 없다. 형제라야 바(10)가 위, 책갈피(9)가 아래가 되어 윗동이
        바에 가린다.
      */}
      {!rail && leaves}
    </>
  );
}
