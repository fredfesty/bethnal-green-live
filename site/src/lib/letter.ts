// Fred's letter at the top of a newsletter issue. `intro` is null until the letter is written, or
// {left_out: true} when Fred chose to send the issue without one; either way the page shows no letter.
export interface Letter { greeting: string; paragraphs: string[]; sign_off: string; signed: string; postscript?: string | null }
export type Intro = Letter | { left_out: true; by: string; at: string } | null;

/** Fred's letter, or null when the issue has none (not written yet, or left out on purpose). */
export const letterOf = (i: { intro: Intro }): Letter | null =>
  i.intro && !("left_out" in i.intro) ? i.intro : null;
