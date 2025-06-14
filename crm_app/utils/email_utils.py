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