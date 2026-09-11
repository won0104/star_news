import { useNavigate } from 'react-router-dom';
import { card, photo } from '../data/assets';
import {
  atticMiniContent,
  eventCard,
  eventContent,
  miniShells,
  statementCard,
  statementContent,
} from '../data/cards';
import { activeNav, footerMotto, hero, navItems, searchPlaceholder, tagline } from '../data/scene';
import { brand } from '../data/home';
import { CompactShell } from '../components/compact/CompactShell';
import { PaperTile } from '../components/compact/PaperTile';
import cards from '../components/compact/CompactCards.module.css';

/**
 * "나의 뉴스 다락방" once the room is too narrow for the pinned composition: the same
 * cards, reflowed into a scrolling column. The yarn, the depth papers and the three
 * wayfinding hints are dropped — all three describe the desktop layout's geometry
 * ("Related stories slide in →", "Tuck away to declutter"), so they have nothing left
 * to point at here.
 */
export function AtticCompact() {
  const navigate = useNavigate();

  return (
    <CompactShell
      backdrop={photo.backdropTrend}
      brand={`${brand.name}  ·  ${brand.section}`}
      brandLabel="홈으로"
      onBrand={() => navigate('/')}
      title={hero.titleLines.join(' ')}
      subtitle={hero.subtitleLines.join(' ')}
      search={searchPlaceholder}
      activeNav={activeNav.label}
      navItems={navItems}
      motto={footerMotto.join('  ')}
      tagline={tagline.lines.join('  ')}
    >
      <div className={cards.stack}>
        <PaperTile paper={eventCard.paper} rotate={eventCard.rotate}>
          <div className={cards.typeRow}>
            <img className={cards.dot} src={card.dot.event} alt="" />
            <p className={`${cards.type} ${cards.typeEvent}`}>{eventContent.type}</p>
          </div>

          <div className={cards.thumb}>
            <img className={cards.thumbPhoto} src={photo.eventThumb} alt="" />
          </div>

          <h2 className={cards.headline}>{eventContent.headlineLines.join(' ')}</h2>

          <div className={cards.metaRow}>
            <p className={cards.meta}>{eventContent.date}</p>
            <p className={cards.meta}>{eventContent.place}</p>
          </div>

          <p className={cards.arrow} aria-hidden>
            →
          </p>
        </PaperTile>

        <PaperTile paper={statementCard.paper} rotate={statementCard.rotate}>
          <div className={cards.typeRow}>
            <img className={cards.dot} src={card.dot.statement} alt="" />
            <p className={cards.type}>{statementContent.type}</p>
          </div>

          <p className={cards.quoteMark} aria-hidden>
            “
          </p>
          <blockquote className={cards.quoteBody}>
            {statementContent.bodyLines.join(' ')}
          </blockquote>
          <p className={cards.quoteSource}>{statementContent.source}</p>
        </PaperTile>
      </div>

      <p className={cards.sectionLabel}>CATEGORIES</p>

      <div className={cards.grid}>
        {miniShells.map((shell) => {
          const content = atticMiniContent[shell.id];
          return (
            <PaperTile
              key={shell.id}
              paper={shell.paper}
              rotate={shell.rotate}
              selectLabel={content.label}
              onSelect={shell.id === 'policy' ? () => navigate('/explore') : undefined}
            >
              <div className={cards.tileBody}>
                <p className={cards.miniGlyph} aria-hidden>
                  {content.glyph}
                </p>
                <div className={cards.tileFoot}>
                  <img className={cards.tileDot} src={content.dot} alt="" />
                  <p className={cards.miniLabel}>{content.label}</p>
                </div>
              </div>
            </PaperTile>
          );
        })}
      </div>
    </CompactShell>
  );
}
