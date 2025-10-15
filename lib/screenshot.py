import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def screenshot_url(url, output_path=None):
    """
    Take a screenshot of a URL.

    Args:
        url: The URL to screenshot
        output_path: Where to save the screenshot (optional, uses temp file if not provided)

    Returns:
        Path to the screenshot
    """
    if output_path is None:
        # Create temp directory if it doesn't exist
        temp_dir = Path('./temp')
        temp_dir.mkdir(exist_ok=True)

        # Create temporary file in the temp directory
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.png',
            delete=False,
            dir=str(temp_dir)  # Use string path of the created directory
        )
        output_path = temp_file.name
        temp_file.close()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 1024})
        page.goto(url)
        page.wait_for_load_state('networkidle')
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path
