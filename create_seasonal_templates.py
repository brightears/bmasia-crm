#!/usr/bin/env python3
"""
Create Seasonal Email Templates for BMAsia CRM
Creates 7 professional seasonal campaign templates via the API
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = "https://bmasia-crm.onrender.com/api/v1"
USERNAME = "admin"
PASSWORD = "bmasia123"

# BMAsia brand colors
BMASIA_ORANGE = "#FFA500"

def get_auth_token():
    """Authenticate and get JWT token"""
    response = requests.post(
        f"{API_BASE_URL}/auth/login/",
        json={"username": USERNAME, "password": PASSWORD}
    )
    if response.status_code == 200:
        return response.json()['access']
    else:
        raise Exception(f"Authentication failed: {response.text}")

def create_html_template(emoji, title, content_paragraphs, cta_text="Reply to this email"):
    """Generate professional HTML email template with BMAsia branding"""

    paragraphs_html = "\n".join([
        f'                                <p style="margin: 0 0 16px 0; line-height: 1.6;">{p}</p>'
        for p in content_paragraphs
    ])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main container -->
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                    <!-- Header with BMAsia orange accent -->
                    <tr>
                        <td style="padding: 0;">
                            <div style="height: 4px; background: linear-gradient(90deg, {BMASIA_ORANGE} 0%, #ff8c00 100%);"></div>
                        </td>
                    </tr>

                    <!-- Logo/Brand area -->
                    <tr>
                        <td style="padding: 32px 40px 24px 40px; text-align: center;">
                            <h1 style="margin: 0; font-size: 32px; color: #333333; font-weight: 600;">
                                {emoji} {title}
                            </h1>
                        </td>
                    </tr>

                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 0 40px 24px 40px;">
                            <p style="margin: 0; font-size: 16px; color: #333333; line-height: 1.6;">
                                Dear <strong>{{{{contact_name}}}}</strong>,
                            </p>
                        </td>
                    </tr>

                    <!-- Main content -->
                    <tr>
                        <td style="padding: 0 40px 32px 40px; font-size: 15px; color: #555555;">
{paragraphs_html}
                        </td>
                    </tr>

                    <!-- Call to action -->
                    <tr>
                        <td style="padding: 0 40px 32px 40px; text-align: center;">
                            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto;">
                                <tr>
                                    <td style="background-color: {BMASIA_ORANGE}; border-radius: 4px; padding: 14px 32px;">
                                        <a href="mailto:production@bmasiamusic.com?subject=Re: {{{{company_name}}}} - {title}"
                                           style="color: #ffffff; text-decoration: none; font-weight: 600; font-size: 15px; display: block;">
                                            {cta_text}
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Signature -->
                    <tr>
                        <td style="padding: 0 40px 32px 40px; font-size: 15px; color: #555555;">
                            <p style="margin: 0 0 8px 0;">Warm regards,</p>
                            <p style="margin: 0; font-weight: 600; color: #333333;">The BMAsia Production Team</p>
                            <p style="margin: 4px 0 0 0; color: #777777;">
                                <a href="mailto:production@bmasiamusic.com" style="color: {BMASIA_ORANGE}; text-decoration: none;">production@bmasiamusic.com</a>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; background-color: #f9f9f9; border-top: 1px solid #eeeeee; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; text-align: center; line-height: 1.5;">
                                © {{{{current_year}}}} BMAsia Music. Creating exceptional soundscapes for your business.
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''
    return html

def create_plain_text(greeting, content_paragraphs):
    """Generate plain text version"""
    paragraphs_text = "\n\n".join(content_paragraphs)

    text = f'''Dear {{{{contact_name}}}},

{paragraphs_text}

Please reply to this email with your preferences, and we'll be happy to assist!

Warm regards,
The BMAsia Production Team
production@bmasiamusic.com

---
© {{{{current_year}}}} BMAsia Music. Creating exceptional soundscapes for your business.'''

    return text

# Template definitions
TEMPLATES = [
    {
        "name": "Christmas Season Music Campaign",
        "template_type": "seasonal_christmas",
        "department": "Music",
        "subject": "🎄 Christmas Music for {{company_name}} - Let's Create Holiday Magic!",
        "emoji": "🎄",
        "title": "Christmas Season Preparation",
        "content": [
            "The festive season is just around the corner, and we wanted to reach out early to help you create the perfect Christmas atmosphere at {{company_name}}.",
            "Our specially curated Christmas music collections feature everything from classic carols to modern holiday favorites, all designed to enhance your customers' seasonal experience and create a warm, welcoming environment.",
            "We offer flexible programming options including traditional Christmas music, contemporary holiday hits, jazzy festive tunes, or a custom blend that matches your brand perfectly.",
            "Would you like us to prepare a special Christmas playlist for your venues? We typically recommend starting the festive music 2-3 weeks before Christmas for optimal impact."
        ],
        "notes": "Send in October (2 months before Christmas). Target all active customers. Increases seasonal engagement and provides opportunity for special playlist customization."
    },
    {
        "name": "Chinese New Year Music Campaign",
        "template_type": "seasonal_newyear",
        "department": "Music",
        "subject": "🧧 Chinese New Year Music for {{company_name}} - Prosperity & Joy!",
        "emoji": "🧧",
        "title": "Chinese New Year Preparation",
        "content": [
            "Chinese New Year is approaching, and we'd love to help {{company_name}} celebrate this important festival with the perfect musical atmosphere!",
            "Our CNY music collections blend traditional festive songs with contemporary Chinese pop hits, creating an uplifting and celebratory mood that resonates with your guests during this auspicious time.",
            "We offer both traditional instrumental options and modern festive tracks, with selections that incorporate lucky prosperity themes perfect for the New Year season.",
            "Would you like us to prepare a special Chinese New Year playlist? The music typically runs for the 15-day celebration period, and we can customize the energy level to match your venue's atmosphere."
        ],
        "notes": "Send 2 weeks before CNY (date varies yearly, typically late January/early February). Target customers in Asia-Pacific region. Cultural celebration music increases customer connection."
    },
    {
        "name": "Valentine's Day Music Campaign",
        "template_type": "seasonal_valentines",
        "department": "Music",
        "subject": "💕 Valentine's Day Music for {{company_name}} - Romance is in the Air!",
        "emoji": "💕",
        "title": "Valentine's Day Preparation",
        "content": [
            "Valentine's Day is coming soon, and we wanted to help you set the perfect romantic mood at {{company_name}}!",
            "Our Valentine's music collections feature timeless love songs, romantic ballads, and smooth contemporary tracks that create an intimate, couple-friendly atmosphere perfect for the season of love.",
            "Whether you prefer classic romantic hits from iconic artists or modern love songs with a contemporary feel, we can create the ideal soundscape to make your venue the perfect date destination.",
            "Shall we prepare a special Valentine's playlist for you? We can also create a gentler, more intimate music flow for this special occasion."
        ],
        "notes": "Send 2 weeks before February 14. Target restaurants, bars, hotels, and hospitality venues. Romantic atmosphere music drives couples' business."
    },
    {
        "name": "Songkran Festival Music Campaign",
        "template_type": "seasonal_songkran",
        "department": "Music",
        "subject": "💦 Songkran Festival Music for {{company_name}} - Thai New Year Celebration!",
        "emoji": "💦",
        "title": "Songkran Preparation",
        "content": [
            "Songkran, Thailand's most celebrated festival, is just around the corner! We'd love to help {{company_name}} create the perfect festive atmosphere for Thai New Year.",
            "Our Songkran music collections feature upbeat Thai favorites, traditional music with a modern twist, and festive tracks that capture the joyful spirit of water festival celebrations.",
            "We offer energetic party mixes perfect for daytime festivities, as well as more relaxed evening selections that maintain the celebratory mood throughout the multi-day festival.",
            "Would you like us to prepare a special Songkran playlist? We can customize the energy levels for different times of day and incorporate both classic Thai songs and contemporary hits."
        ],
        "notes": "Send 2 weeks before April 13. Target Thailand customers only. Songkran is the biggest celebration in Thailand - music drives festive atmosphere and local cultural connection."
    },
    {
        "name": "Loy Krathong Festival Music Campaign",
        "template_type": "seasonal_loy_krathong",
        "department": "Music",
        "subject": "🪷 Loy Krathong Music for {{company_name}} - Festival of Lights!",
        "emoji": "🪷",
        "title": "Loy Krathong Preparation",
        "content": [
            "The beautiful Loy Krathong festival is approaching, and we'd love to help {{company_name}} create the perfect atmosphere for this magical evening of lights and water.",
            "Our Loy Krathong music collections feature traditional Thai melodies, peaceful instrumental pieces, and romantic songs that complement the serene and mystical mood of the floating lantern festival.",
            "This festival calls for gentler, more reflective music that enhances the romantic and spiritual atmosphere as guests enjoy the beauty of candlelit krathongs floating on water.",
            "Would you like us to prepare a special Loy Krathong playlist? We typically recommend peaceful, romantic Thai music that creates a magical ambiance perfect for this special evening."
        ],
        "notes": "Send 2 weeks before Loy Krathong (November, full moon date varies). Target Thailand customers. Romantic/peaceful music matches the serene, mystical festival atmosphere."
    },
    {
        "name": "Ramadan Music Campaign",
        "template_type": "seasonal_ramadan",
        "department": "Music",
        "subject": "🌙 Ramadan Music for {{company_name}} - A Month of Reflection",
        "emoji": "🌙",
        "title": "Ramadan Preparation",
        "content": [
            "As the blessed month of Ramadan approaches, we wanted to offer our support in creating an appropriate and respectful atmosphere at {{company_name}}.",
            "Our Ramadan music selections feature peaceful instrumental pieces, calming world music, and culturally appropriate tracks that create a serene environment suitable for this holy month of reflection and prayer.",
            "We understand the importance of maintaining a respectful atmosphere during Ramadan, and our music selections are carefully curated to be gentle, non-intrusive, and culturally sensitive.",
            "Would you like us to adjust your music programming for Ramadan? We can provide calming, instrumental-focused playlists that honor the spirit of this sacred time."
        ],
        "notes": "Send 2 weeks before Ramadan (date varies yearly, follows Islamic calendar). Target Middle East customers and venues in Muslim-majority areas. Respectful, calming music appropriate for holy month."
    },
    {
        "name": "Singapore National Day Music Campaign",
        "template_type": "seasonal_singapore_national_day",
        "department": "Music",
        "subject": "🇸🇬 Singapore National Day Music for {{company_name}} - Celebrate Our Nation!",
        "emoji": "🇸🇬",
        "title": "Singapore National Day Preparation",
        "content": [
            "Singapore's National Day is coming up on August 9th, and we'd love to help {{company_name}} celebrate our nation's birthday in style!",
            "Our National Day music collections feature beloved patriotic songs, Singaporean artists' greatest hits, and celebratory tracks that capture the pride and joy of our independence celebration.",
            "From timeless NDP (National Day Parade) classics to contemporary Singaporean music, we can create a playlist that brings together the spirit of unity and celebration that defines our national day.",
            "Would you like us to prepare a special National Day playlist? We can incorporate both traditional patriotic songs and modern Singaporean hits to create the perfect celebratory atmosphere."
        ],
        "notes": "Send 2 weeks before August 9. Target Singapore customers only. Patriotic/celebratory music drives national pride and community connection during Singapore's most important holiday."
    }
]

def create_template(token, template_data):
    """Create a single email template via API"""

    # Generate HTML
    html_body = create_html_template(
        emoji=template_data["emoji"],
        title=template_data["title"],
        content_paragraphs=template_data["content"]
    )

    # Generate plain text
    plain_text = create_plain_text(
        greeting=f"Dear {{{{contact_name}}}},",
        content_paragraphs=template_data["content"]
    )

    # Prepare API payload
    payload = {
        "name": template_data["name"],
        "template_type": template_data["template_type"],
        "language": "en",
        "subject": template_data["subject"],
        "body_html": html_body,
        "body_text": plain_text,
        "is_active": True,
        "department": template_data["department"],
        "notes": template_data["notes"]
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{API_BASE_URL}/email-templates/",
        headers=headers,
        json=payload
    )

    return response

def main():
    """Main execution"""
    print("=" * 70)
    print("BMAsia CRM - Seasonal Email Template Creator")
    print("=" * 70)
    print()

    # Authenticate
    print("🔐 Authenticating...")
    try:
        token = get_auth_token()
        print("✅ Authentication successful!")
        print()
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return

    # Create templates
    results = {
        "success": [],
        "failed": []
    }

    print(f"📧 Creating {len(TEMPLATES)} seasonal email templates...")
    print()

    for i, template_data in enumerate(TEMPLATES, 1):
        template_name = template_data["name"]
        template_type = template_data["template_type"]

        print(f"[{i}/{len(TEMPLATES)}] Creating: {template_name}")
        print(f"    Type: {template_type}")
        print(f"    Department: {template_data['department']}")

        try:
            response = create_template(token, template_data)

            if response.status_code == 201:
                print(f"    ✅ SUCCESS - Template created")
                results["success"].append(template_name)
            elif response.status_code == 400 and "already exists" in response.text.lower():
                print(f"    ⚠️  SKIPPED - Template already exists")
                results["success"].append(template_name + " (already exists)")
            else:
                print(f"    ❌ FAILED - Status {response.status_code}")
                print(f"    Error: {response.text[:200]}")
                results["failed"].append(f"{template_name}: {response.status_code}")
        except Exception as e:
            print(f"    ❌ FAILED - Exception: {e}")
            results["failed"].append(f"{template_name}: {str(e)}")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Successful: {len(results['success'])}")
    for item in results["success"]:
        print(f"   - {item}")
    print()

    if results["failed"]:
        print(f"❌ Failed: {len(results['failed'])}")
        for item in results["failed"]:
            print(f"   - {item}")
        print()

    print("=" * 70)
    print("🎉 Template creation process complete!")
    print()
    print("Next steps:")
    print("1. View templates at: https://bmasia-crm.onrender.com/admin/crm_app/emailtemplate/")
    print("2. Test templates by creating seasonal campaigns")
    print("3. Schedule campaigns using email sequences for automated delivery")
    print("=" * 70)

if __name__ == "__main__":
    main()
