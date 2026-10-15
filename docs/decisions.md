# Decisions

Product and working decisions Fred has made along the way, written down so everyone working on the project (people and their Claude) follows the same ones. To change one, open an issue and ask Fred; once agreed, update this file in the same pull request as the change.

## How we work

- **Every change ships end to end** (October 2026): an issue, the change, unit tests where they make sense, a pull request, an independent review, fixes, conflicts resolved, merged. How: [`docs/ship-issue.md`](ship-issue.md).
- **For now, finished pull requests are merged without waiting for Fred** (October 2026), once every check has passed. Exceptions: newsletter issues (Fred reads them first), anything labelled `needs-fred`, and a collaborator's changes to the files that steer the scheduled runs (listed in `docs/ship-issue.md`, step 8), which wait for Fred.
- **Pull request links are always clickable**: give them as markdown hyperlinks in reports and messages.
- **Scheduled runs auto-publish for now**: while the `AUTO_MERGE` repository variable is `true`, GitHub merges a run's pull request once its checks pass. The venue stories run is always merged: if GitHub hasn't merged it, the run merges its own pull request once every check has passed.
- **Finding and enriching are separate jobs**: agents that look for new events are not the ones that update or enrich existing ones (descriptions, contact details, links).

## Accuracy and fairness to other sites

- **Hard limits on other people's websites** (October 2026): at most 20 pages per website per run, so nobody is upset by us, and in the morning run at most 5 web searches per agent. Other runs have their own search limits (8 per venue storyteller; the weekly venue run's are in `docs/venue-run.md`). They are counted and enforced by `scripts/budget.py` for the scouts, the verifier and the storytellers (14 October 2026). The two nights scouts share one allowance per website.
- **Credit and link our sources** (October 2026, "very important"): when the site or a story uses something from another site (Time Out, Londonist, a venue guide…), it names that site and the name links to the exact page it came from, so we credit them and send readers there rather than look like we're taking their data.
- **Primary listings**: DesignMyNight is Backyard Comedy Club's primary listing (14 October 2026).

## The website

- **Google Maps, not OpenStreetMap**, for every map and "find it on a map" link.
- **A page for every venue**: what it's like, the music, the crowd, accessibility, cost. **Every listed event links to its venue's page.**
- **Every listed event has a short description** in our own words (the listing writer), today's events first, then the soonest.
- **Longer venue descriptions**: a venue whose description is under 15 lines gets its own research agent in the weekly venue run (when it opened, what changed since, what it does now, the vibe, interesting facts). If nothing turns up, it's tried again a week later, not daily.
- **Held events need a fast review**: show the data and a yes or no to click (wanted; not built yet).
- **Health & wellness** is a category (issue #21), covering places such as AndSoul Sanctuary Sauna and Wellness Studio, MoreYoga Bethnal Green and Mission (7–9 Fashion Street, E1).

## The runs

- **Morning run, daily**: six scouts, the verifier, the listing writer, the event storytellers and their checker. Nights & music is split into two scouts, club & DJ nights and gigs & live music (14 October 2026). Outer-zone gigs are scouted every day, not only on Mondays (14 October 2026).
- **Weekly venue run, Sundays**: cheap finders and researchers (Haiku) look for new venues and research reviews, event types, past listings and music; an editor (Sonnet) compares with what's published and updates the venue guide. A second Sunday session writes the longer venue stories.
- **Newsletter, weekly**: laid out by AI, with a short, human-sounding letter at the top written by Opus and signed by Fred, in the spirit of Cat's note in Peckham.Live. Fred reads each issue and sends it himself.
