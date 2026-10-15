// Fred's letter at the top of a newsletter issue. `intro` is null until the letter is written (the issue
// isn't ready and gets no page), or {left_out: true} when Fred chose to send the issue without one (it is
// ready, and its page simply has no letter).
export interface Letter { greeting: string; paragraphs: string[]; sign_off: string; signed: string; postscript?: string | null }
export type Intro = Letter | { left_out: true; by: "fred"; at: string } | null;

/** Fred's letter, or null when the issue has none (not written yet, or left out on purpose). */
export const letterOf = (i: { intro: Intro }): Letter | null =>
  i.intro && !("left_out" in i.intro) ? i.intro : null;

/** An issue is ready (listed, with a page) once its letter is written or Fred has left it out on purpose. */
export const isReady = (i: { intro: Intro }): boolean => !!i.intro;
