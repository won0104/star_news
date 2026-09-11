import { yarnFibers, yarnStrands } from '../../data/scene';
import { BleedImage } from './BleedImage';

/** The five coloured threads strung across the room, plus their shadow pass. */
export function YarnStrands() {
  return <>
      {yarnStrands.map(strand => <BleedImage key={strand.src} {...strand} />)}
    </>;
}

/** Fibre highlights, drawn after the depth papers so the threads keep their sheen. */
export function YarnFibers() {
  return <>
      {yarnFibers.map(fiber => <BleedImage key={fiber.src} {...fiber} />)}
    </>;
}
