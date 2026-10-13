// Things a person decides. Change them here; nothing else needs editing.
export default {
  name: "Bethnal Green Live",
  district: "E2",
  tagline: "What's on around Bethnal Green, checked before it's listed.",

  // Newsletter: the Buttondown username (buttondown.com/<username>). The sign-up form posts to it.
  // Required: the tests fail if it's empty. Never put the Buttondown API key here; it's the BUTTONDOWN_API_KEY secret.
  buttondownUsername: "bethnalgreenlive",

  // Where readers report a wrong listing. An email address, or a form URL. Leave empty to hide the link.
  correctionsContact: "",

  // How many days ahead the listings show.
  daysAhead: 28,
};
