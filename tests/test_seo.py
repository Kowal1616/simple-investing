import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYOUT = os.path.join(os.path.dirname(ROOT), 'templates', 'layout.html')

def test_layout_has_canonical_and_social_tags():
    with open(LAYOUT, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'rel="canonical"' in content, "Canonical link should be present in layout.html"
    assert 'og:image' in content, "OG image tag should be present in layout.html"
    assert 'twitter:card' in content, "Twitter Card tag should be present in layout.html"
