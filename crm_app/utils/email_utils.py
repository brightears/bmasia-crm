"""
Email utilities for CRM app
"""

import re


def text_to_html(text):
    """
    Convert plain text to HTML format for emails
    Preserves formatting and makes links clickable
    """
    if not text:
        return ""
    
    # Escape HTML characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Convert line breaks to <br> tags
    text = text.replace('\n', '<br>\n')
    
    # Convert URLs to clickable links
    url_pattern = r'(https?://[^\s]+)'
    text = re.sub(url_pattern, r'<a href="\1">\1</a>', text)
    
    # Convert email addresses to mailto links
    email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    text = re.sub(email_pattern, r'<a href="mailto:\1">\1</a>', text)
    
    # Wrap in basic HTML template
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            {text}
        </div>
    </body>
    </html>
    """
    
    return html


def html_to_text(html):
    """
    Convert HTML to plain text for email fallback.
    Strips HTML tags while preserving readability.

    Args:
        html (str): HTML content

    Returns:
        str: Plain text version
    """
    if not html:
        return ''

    from html import unescape

    # Unescape HTML entities first
    text = unescape(html)

    # Convert <br> and <p> tags to newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)

    # Convert list items to bullets
    text = re.sub(r'<li[^>]*>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
    text = text.strip()

    return text