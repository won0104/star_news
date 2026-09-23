import { Fragment, useLayoutEffect, useRef, useState } from 'react';
import { authActions, brand, navItems } from '../../data/home';
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
  const rail = useHasNavRail();
  // 레일에서는 늘 펼쳐져 있으므로 이 값은 상단바일 때만 읽는다.
  const [searchOpen, setSearchOpen] = useState(false);

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

  return (
    <header className={`${styles.bar} ${nightGlass ? styles.nightGlass : ''}`}>
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

      <nav ref={navRef} className={styles.nav}>
        {navItems.map((item, index) => (
          <Fragment key={item.id}>
            {index > 0 && <span className={styles.navRule} aria-hidden />}
            {/*
              누르기 전에 한 번 알린다 — 포인터가 올라오거나 탭 이동으로 초점이 닿는 순간이
              목적지를 고른 순간에 가장 가깝다. 무엇을 미리 할지는 받는 쪽이 정한다.
            */}
            <button
              type="button"
              className={`${styles.navItem} ${item.id === activeId ? styles.navItemActive : ''}`}
              aria-current={item.id === activeId ? 'page' : undefined}
              onPointerEnter={() => onIntent?.(item.id)}
              onFocus={() => onIntent?.(item.id)}
              onClick={() => onSelect(item.id)}
            >
              {item.label}
            </button>
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
  );
}
