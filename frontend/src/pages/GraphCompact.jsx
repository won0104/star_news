import { useNavigate } from 'react-router-dom';
import { card, graph } from '../data/assets';
import { eventCard, miniShells, statementCard } from '../data/cards';
import {
  graphActiveNav,
  graphControls,
  graphEntityContent,
  graphEventContent,
  graphHero,
  graphMotto,
  graphNavItems,
  graphSearchPlaceholder,
  graphStatementContent,
  graphTagline,
  relationChips,
} from '../data/graph';
import { CompactShell } from '../components/compact/CompactShell';
import { PaperTile } from '../components/compact/PaperTile';
import cards from '../components/compact/CompactCards.module.css';

const COLUMNS = [0, 1, 2, 3, 4];

/**
 * Graph exploration, reflowed. The hanging threads are what the narrow layout cannot
 * keep — they are drawn between fixed card coordinates — so the relation each
 * neighbour has to the centre is carried by the chip row instead of by a coloured
 * thread, and the neighbours follow the centre event in reading order.
 */
export function GraphCompact() {
  const navigate = useNavigate();

  return (
    <CompactShell
      brand={graphHero.brand}
      brandLabel="다락방으로 돌아가기"
      onBrand={() => navigate('/')}
      title={graphHero.titleLines.join(' ')}
      subtitle={graphHero.subtitleLines.join(' ')}
      search={graphSearchPlaceholder}
      activeNav={graphActiveNav.label}
      navItems={graphNavItems}
      motto={graphMotto.join('  ·  ')}
      tagline={graphTagline.lines.join('  ·  ')}
    >
      <div className={cards.stack}>
        <PaperTile paper={eventCard.paper} rotate={eventCard.rotate}>
          <div className={cards.typeRow}>
            <img className={cards.dot} src={card.dot.event} alt="" />
            <p className={`${cards.type} ${cards.typeEvent}`}>{graphEventContent.type}</p>
            <p className={cards.bookmark} aria-hidden>
              {graphEventContent.bookmark}
            </p>
          </div>

          <div className={cards.bankThumb}>
            <img className={cards.bankRoof} src={graph.bankRoof} alt="" />
            <div className={cards.bankColumns}>
              {COLUMNS.map((index) => (
                <div key={index} className={cards.bankColumn} />
              ))}
            </div>
            <div className={cards.bankBase} />
            <p className={cards.bankCaption}>{graphEventContent.thumbnailCaption}</p>
          </div>

          <h2 className={cards.headline}>{graphEventContent.headlineLines.join(' ')}</h2>

          <div className={cards.metaRow}>
            <p className={cards.meta}>{graphEventContent.category}</p>
            <p className={cards.meta}>{graphEventContent.articles}</p>
          </div>

          <p className={cards.arrow} aria-hidden>
            →
          </p>
        </PaperTile>

        <PaperTile paper={statementCard.paper} rotate={statementCard.rotate}>
          <div className={cards.typeRow}>
            <img className={cards.dot} src={card.dot.statement} alt="" />
            <p className={`${cards.type} ${cards.typeStatement}`}>{graphStatementContent.type}</p>
          </div>

          <p className={cards.quoteMark} aria-hidden>
            “
          </p>
          <blockquote className={cards.quoteBody}>
            {graphStatementContent.bodyLines.join(' ')}
          </blockquote>
          <p className={cards.quoteSource}>{graphStatementContent.source}</p>
        </PaperTile>
      </div>

      <div className={cards.controls}>
        <p className={cards.controlsEyebrow}>{graphControls.eyebrow}</p>
        <div className={cards.controlsRow}>
          <button type="button" className={`${cards.controlChip} ${cards.chipSolid}`}>
            {graphControls.depth}
          </button>
          <button type="button" className={`${cards.controlChip} ${cards.chipGhost}`}>
            {graphControls.count}
          </button>
          <button type="button" className={`${cards.controlChip} ${cards.chipDark}`}>
            {graphControls.more}
          </button>
        </div>
      </div>

      <p className={cards.sectionLabel}>연결된 지식</p>

      <div className={cards.chipRow}>
        {relationChips.map((chip) => (
          <div key={chip.id} className={cards.relationChip}>
            <img className={cards.relationDot} src={chip.dot} alt="" />
            {chip.label}
          </div>
        ))}
      </div>

      <div className={cards.grid}>
        {miniShells.map((shell) => {
          const content = graphEntityContent[shell.id];
          return (
            <PaperTile key={shell.id} paper={shell.paper} rotate={shell.rotate}>
              <div className={cards.tileBody}>
                <p className={cards.entityType} style={{ color: content.typeColor }}>
                  {content.type}
                </p>
                <p className={cards.entityTitle}>{content.titleLines.join(' ')}</p>
                <div className={cards.tileFoot}>
                  <img className={cards.tileDot} src={content.dot} alt="" />
                  <p className={cards.entitySub}>{content.sub}</p>
                </div>
              </div>
            </PaperTile>
          );
        })}
      </div>
    </CompactShell>
  );
}
