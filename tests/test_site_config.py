"""The site settings a person decides stay usable: the newsletter sign-up form has a Buttondown account behind it."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "site/src/site.config.mjs"
SUBSCRIBE = REPO / "site/src/components/Subscribe.astro"


def setting(name):
    m = re.search(rf'^\s*{name}:\s*["\']([^"\']*)["\']', CONFIG.read_text(encoding="utf-8"), re.M)
    assert m, f"{name} is missing from site.config.mjs"
    return m.group(1)


def test_newsletter_username_is_set():
    # Empty hides the sign-up form and shows "the newsletter starts soon" instead.
    assert setting("buttondownUsername"), "buttondownUsername is empty, so the site has no sign-up form"


def test_newsletter_username_looks_like_a_buttondown_username():
    user = setting("buttondownUsername")
    assert re.fullmatch(r"[a-z0-9_-]+", user), f"{user!r} is not a Buttondown username (use the part after buttondown.com/)"


def test_form_posts_to_buttondown_with_the_username():
    src = SUBSCRIBE.read_text(encoding="utf-8")
    assert re.search(r"https://buttondown\.com/api/emails/embed-subscribe/\$\{\s*\w+\s*\}", src)
    assert 'method="post"' in src
    assert 'name="email"' in src and 'type="email"' in src
    assert 'name="embed"' in src


def test_no_api_key_in_the_site_settings():
    # The API key belongs in the BUTTONDOWN_API_KEY repository secret, never in a file.
    text = CONFIG.read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
