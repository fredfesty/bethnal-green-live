// "The story" on an event page, written by the event storyteller and stamped by the event story checker.
// It is shown only once its review is newer than its words, so an unchecked story never reaches readers.
import type { StoryEvidence } from "./storylinks";

export interface EventStory {
  who?: string | null; started?: string | null; then?: string | null; now?: string | null; vibe?: string | null;
  worth_knowing?: string[]; written_at: string; evidence: StoryEvidence[];
  review?: { checked_at: string; removed_fields: string[] } | null;
}

export function shownStory(story: EventStory | null | undefined): EventStory | null {
  if (!story?.review?.checked_at) return null;
  if (Date.parse(story.review.checked_at) < Date.parse(story.written_at)) return null;
  const any = story.who || story.started || story.then || story.now || story.vibe || (story.worth_knowing?.length ?? 0) > 0;
  return any ? story : null;
}
