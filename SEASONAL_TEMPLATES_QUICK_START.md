# Seasonal Email Templates - Quick Start Guide

## 🚀 Create All Templates in 30 Seconds

### Step 1: Install Dependencies (if needed)
```bash
pip install requests
```

### Step 2: Run the Script
```bash
cd "/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM"
python3 create_seasonal_templates.py
```

### Step 3: Verify in Admin
Navigate to: https://bmasia-crm.onrender.com/admin/crm_app/emailtemplate/

You should see 7 new templates:
1. ✅ Christmas Season Music Campaign
2. ✅ Chinese New Year Music Campaign
3. ✅ Valentine's Day Music Campaign
4. ✅ Songkran Festival Music Campaign
5. ✅ Loy Krathong Festival Music Campaign
6. ✅ Ramadan Music Campaign
7. ✅ Singapore National Day Music Campaign

---

## 📧 What Gets Created

Each template includes:
- ✅ **Professional HTML email** with BMAsia orange branding (#FFA500)
- ✅ **Plain text version** for accessibility
- ✅ **Variable support**: {{contact_name}}, {{company_name}}, {{current_year}}
- ✅ **Department routing** to production@bmasiamusic.com
- ✅ **Mobile-responsive design**
- ✅ **Clear call-to-action button**
- ✅ **BMAsia signature and branding**

---

## 📅 Annual Campaign Calendar

| Month | Campaign | Send Date | Target |
|-------|----------|-----------|--------|
| **Jan** | Chinese New Year | 2 weeks before CNY | APAC |
| **Jan** | Valentine's Day | Late Jan (2 weeks before Feb 14) | F&B, Hotels |
| **Mar** | Songkran | Late Mar (2 weeks before Apr 13) | Thailand |
| **Jul** | Singapore National Day | Late Jul (2 weeks before Aug 9) | Singapore |
| **Oct** | Christmas | Early Oct (2 months before Dec 25) | All customers |
| **Oct** | Loy Krathong | Late Oct (2 weeks before festival) | Thailand |
| **Varies** | Ramadan | 2 weeks before Ramadan | Middle East |

---

## 🎯 Campaign Setup (5 Minutes)

### For Each Seasonal Campaign:

1. **Go to Email Automations**
   - Navigate to: https://bmasia-crm-frontend.onrender.com/email-automations

2. **Create New Sequence**
   - Click "Create New Automation"
   - Name: "Christmas 2026 Campaign" (or relevant season)
   - Type: Manual
   - Select the seasonal template

3. **Add Sequence Step**
   - Delay: 0 days (send immediately)
   - Send time: 09:00 (9 AM local time)
   - Select template: "seasonal_christmas" (or relevant)

4. **Enroll Customers**
   - Filter by country (e.g., Thailand only for Songkran)
   - Select active customers
   - Bulk enroll

5. **Activate**
   - Review settings
   - Activate sequence
   - Monitor results

---

## 🎨 Template Details

### 1. Christmas (seasonal_christmas)
- **Emoji**: 🎄
- **Timing**: October (2 months advance)
- **Target**: All markets
- **Subject**: "🎄 Christmas Music for {{company_name}} - Let's Create Holiday Magic!"

### 2. Chinese New Year (seasonal_newyear)
- **Emoji**: 🧧
- **Timing**: 2 weeks before CNY
- **Target**: APAC (Singapore, Hong Kong, Thailand, Malaysia)
- **Subject**: "🧧 Chinese New Year Music for {{company_name}} - Prosperity & Joy!"

### 3. Valentine's Day (seasonal_valentines)
- **Emoji**: 💕
- **Timing**: Late January (2 weeks before Feb 14)
- **Target**: Restaurants, bars, hotels
- **Subject**: "💕 Valentine's Day Music for {{company_name}} - Romance is in the Air!"

### 4. Songkran (seasonal_songkran)
- **Emoji**: 💦
- **Timing**: Late March (2 weeks before Apr 13)
- **Target**: Thailand only
- **Subject**: "💦 Songkran Festival Music for {{company_name}} - Thai New Year Celebration!"

### 5. Loy Krathong (seasonal_loy_krathong)
- **Emoji**: 🪷
- **Timing**: Late October (2 weeks before festival)
- **Target**: Thailand only
- **Subject**: "🪷 Loy Krathong Music for {{company_name}} - Festival of Lights!"

### 6. Ramadan (seasonal_ramadan)
- **Emoji**: 🌙
- **Timing**: 2 weeks before Ramadan (date varies)
- **Target**: Middle East, Muslim-majority areas
- **Subject**: "🌙 Ramadan Music for {{company_name}} - A Month of Reflection"

### 7. Singapore National Day (seasonal_singapore_national_day)
- **Emoji**: 🇸🇬
- **Timing**: Late July (2 weeks before Aug 9)
- **Target**: Singapore only
- **Subject**: "🇸🇬 Singapore National Day Music for {{company_name}} - Celebrate Our Nation!"

---

## 📊 Expected Results

### Email Performance Targets
- **Open Rate**: 25-35% (vs. industry avg 15-20%)
- **Response Rate**: 10-15% actual customer replies
- **Conversion Rate**: 5-10% to seasonal playlist creation

### High-Performing Campaigns
- **Songkran (Thailand)**: 30-40% engagement (most important Thai holiday)
- **Singapore National Day**: 35-45% engagement (strong national pride)
- **Chinese New Year (APAC)**: 20-25% engagement (cultural celebration)

### Lower But Valuable Campaigns
- **Valentine's Day (F&B)**: 10-15% engagement (niche but high-value)
- **Ramadan (Middle East)**: 15-20% engagement (demonstrates cultural sensitivity)

---

## 🔧 Troubleshooting

### Script Fails to Run
```bash
# Check Python version (needs 3.7+)
python3 --version

# Install requests if missing
pip install requests

# Check you're in the right directory
pwd
# Should show: .../BMAsia CRM
```

### Authentication Error
- Verify admin credentials: username=`admin`, password=`bmasia123`
- Check API is accessible: https://bmasia-crm.onrender.com/api/v1/
- Ensure backend service is running on Render

### Template Already Exists
- Script will skip existing templates automatically
- To recreate: Delete template in admin panel first
- Or manually edit existing template

### Emails Not Sending
1. Check template `is_active = True`
2. Verify `department = "Music"`
3. Ensure SMTP configured (production@bmasiamusic.com)
4. Check sequence is activated
5. Verify enrollments are "active" status

---

## 💡 Pro Tips

### 1. Test Before Bulk Sending
```
- Enroll 1-2 test contacts first
- Send to your own email
- Check rendering on mobile + desktop
- Verify all variables populate correctly
```

### 2. Segment Properly
```
Christmas → All active customers
Songkran → country = "Thailand" only
Singapore National Day → country = "Singapore" only
Valentine's Day → venue_type IN ("Restaurant", "Bar", "Hotel")
```

### 3. Optimize Send Times
```
Best open rates: 9 AM - 11 AM local time
Avoid: Weekends, late evening, early morning
Respect time zones: 9 AM Singapore time ≠ 9 AM Bangkok time
```

### 4. Follow Up
```
Day 0: Initial campaign sent
Day 7: Follow up to non-openers (different subject line)
Day 14: Final reminder with urgency/deadline
Track: Who opened, who responded, who converted
```

### 5. Personalize When Possible
```
Generic: "Dear Customer"
Better: "Dear {{contact_name}}"
Best: "Dear John, for your 3 Hilton Pattaya locations..."
```

---

## 📈 Measuring Success

### In Django Admin
Navigate to: **Email Logs** → Filter by template_type

Metrics to track:
- Total sent
- Delivery rate (sent / total)
- Open rate (opened / sent)
- Response rate (actual replies)

### In Email Automations UI
View each sequence:
- Enrollments: How many customers enrolled
- Completed: How many finished the sequence
- Active: How many still in progress
- Unsubscribed: Respect their preferences

### Business Impact
Track in contracts/opportunities:
- Revenue from seasonal playlist services
- Customer satisfaction feedback
- Renewal rate impact (engaged customers renew more)
- Referrals from satisfied seasonal services

---

## 🆘 Need Help?

### Documentation
- **Full Guide**: `SEASONAL_EMAIL_TEMPLATES_SUMMARY.md`
- **Email System**: `EMAIL_SYSTEM_STATUS.md`
- **User SMTP Setup**: `USER_SMTP_SETUP_GUIDE.md`

### Support Contacts
- **Technical**: keith@bmasiamusic.com
- **Music Programming**: production@bmasiamusic.com
- **Admin**: norbert@bmasiamusic.com

### Common Questions

**Q: Can I edit templates after creation?**
A: Yes! Edit in Django admin: /admin/crm_app/emailtemplate/

**Q: Can I create Thai language versions?**
A: Yes! Duplicate template and set language = 'th'

**Q: How do I add more variables?**
A: Variables come from context in email_service.py. Contact developer to add more.

**Q: Can I schedule campaigns in advance?**
A: Yes! Use email sequences with future start dates.

**Q: What if customer unsubscribes?**
A: System automatically excludes unsubscribed contacts from all campaigns.

---

## ✅ Success Checklist

Before launching your first campaign:

- [ ] Templates created successfully (run script)
- [ ] Templates verified in admin panel
- [ ] Test email sent to your own address
- [ ] Email renders correctly on mobile
- [ ] Email renders correctly on desktop
- [ ] Variables populate correctly
- [ ] CTA button works (mailto: link)
- [ ] Sequence created with proper timing
- [ ] Segmentation rules applied (geographic/venue type)
- [ ] Test enrollments completed successfully
- [ ] Production enrollments ready
- [ ] Metrics tracking set up
- [ ] Follow-up sequence planned

---

**Ready to launch?** Run the script and start your first seasonal campaign! 🚀

---

**Created**: January 4, 2026
**Version**: 1.0
**Quick Start Guide for BMAsia CRM Seasonal Email Campaigns**
