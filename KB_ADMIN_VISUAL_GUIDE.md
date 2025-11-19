# Knowledge Base Admin Interface - Visual Guide

## Admin Interface Overview

This guide shows what each admin interface looks like and how to use them effectively.

---

## 1. KB Categories Admin

**Access**: Django Admin → CRM_APP → KB Categories

### List View Features:
```
NAME                    PARENT           PUBLISHED ARTICLES    DISPLAY ORDER    IS ACTIVE    ICON
Account Management      -                [5]                   0                ✓           user
Payment Issues          Account Mgmt     [3]                   10               ✓           dollar-sign
Technical Issues        -                [12]                  20               ✓           wrench
```

### Key Features:
- **Green badge** shows article count (only published articles)
- **Hierarchical display** shows parent-child relationships
- **Inline child editor** allows creating subcategories directly
- **Bulk actions**: Activate/Deactivate multiple categories at once

### Form Layout:
```
Basic Information
├── Name: [Payment Issues]
├── Slug: [payment-issues] (auto-generated)
├── Description: [Issues related to payments and billing]
└── Parent: [Account Management] (dropdown)

Display Settings
├── Icon: [dollar-sign]
├── Display Order: [10]
└── Is Active: [✓]

Timestamps (collapsed)
├── Created at: 2025-01-19 10:30:45
└── Updated at: 2025-01-19 10:30:45
```

---

## 2. KB Tags Admin

**Access**: Django Admin → CRM_APP → KB Tags

### List View Features:
```
NAME              COLOR                    ARTICLES       SLUG
urgent            [#F44336] (red badge)    [8]           urgent
billing           [#4CAF50] (green badge)  [12]          billing
technical         [#2196F3] (blue badge)   [15]          technical
```

### Key Features:
- **Color preview** shows actual color in badge format
- **Blue badge** shows article count
- **Simple interface** for quick tag creation

### Form Layout:
```
Tag Information
├── Name: [urgent]
├── Slug: [urgent] (auto-generated)
└── Color: [#F44336] (hex color picker)

Timestamps (collapsed)
├── Created at: 2025-01-19 10:30:45
└── Updated at: 2025-01-19 10:30:45
```

---

## 3. KB Articles Admin (MAIN INTERFACE)

**Access**: Django Admin → CRM_APP → KB Articles

### List View Features:
```
ARTICLE #         TITLE                      CATEGORY          STATUS         VISIBILITY      AUTHOR    VIEWS     HELPFULNESS           PUBLISHED        FEATURED
KB-20251119-0001  How to Reset Password      Account Mgmt      [Published]    [Public]        admin     152       [85.5%] (20 votes)   2025-01-15       ★
KB-20251119-0002  Payment Methods Guide      Billing           [Draft]        [Internal]      john      8         [No votes]           -                ☆
KB-20251118-0012  Troubleshooting Audio      Technical         [Published]    [Public]        sarah     45        [62.0%] (15 votes)   2025-01-10       ☆
```

### Status Badge Colors:
- **Green** [Published] - Article is live
- **Orange** [Draft] - Work in progress
- **Gray** [Archived] - No longer active

### Visibility Badge Colors:
- **Blue** [Public] - Visible to customers
- **Purple** [Internal] - Staff only

### Helpfulness Color Coding:
- **Green badge** >70% - Excellent article
- **Yellow badge** 40-70% - Good article
- **Red badge** <40% - Needs improvement
- **Gray text** "No votes" - Newly published

### Featured Status:
- **Gold star** ★ - Featured on KB homepage
- **Gray star** ☆ - Not featured

### Form Layout:
```
Content
├── Title: [How to Reset Your Password]
├── Slug: [how-to-reset-your-password] (auto-generated)
├── Content: [Large text area - HTML supported]
├── Excerpt: [Short summary...] (auto-generated if empty)
├── Category: [Account Management] (dropdown)
└── Tags: [✓ urgent] [✓ account] [✓ password] (multi-select)

Publishing
├── Status: [Published ▼] (Draft/Published/Archived)
├── Visibility: [Public ▼] (Public/Internal)
├── Author: [admin] (auto-filled)
├── Featured: [✓] (checkbox)
├── Published at: 2025-01-15 14:30:00 (auto-filled on publish)
└── Preview: [View Article →] (link)

Metadata (collapsed)
└── Article Number: KB-20251119-0001 (auto-generated, read-only)

Statistics (collapsed)
├── View Count: 152 (read-only)
├── Helpful Count: 17 (read-only)
└── Not Helpful Count: 3 (read-only)

Timestamps (collapsed)
├── Created at: 2025-01-15 14:30:00
└── Updated at: 2025-01-15 14:30:00

INLINE: Attachments
┌────────────────────────────────────────────────────────────┐
│ FILE                    FILENAME              SIZE         │
│ [Browse...] guide.pdf   guide.pdf             2.5 MB      │
│ [Browse...] screenshot.png screenshot.png     450 KB      │
└────────────────────────────────────────────────────────────┘

INLINE: Related Articles
┌────────────────────────────────────────────────────────────┐
│ TO ARTICLE                    RELATION TYPE    ORDER       │
│ [KB-20251119-0005] (search)   Related ▼        0          │
│ [KB-20251118-0012] (search)   Prerequisite ▼   10         │
└────────────────────────────────────────────────────────────┘
```

### Bulk Actions:
1. **Publish selected articles** - Changes status to Published, sets published_at
2. **Archive selected articles** - Changes status to Archived
3. **Mark as featured** - Sets featured=True
4. **Remove from featured** - Sets featured=False
5. **Export to CSV** - Downloads timestamped CSV with all data

---

## 4. KB Article Views Admin (Analytics)

**Access**: Django Admin → CRM_APP → KB Article Views

### List View Features:
```
ARTICLE #         ARTICLE                    USER            IP ADDRESS         VIEWED AT
KB-20251119-0001  How to Reset Password      john_doe        192.168.1.100      2025-01-19 10:30:45
KB-20251119-0002  Payment Methods Guide      Anonymous       203.45.67.89       2025-01-19 10:28:12
KB-20251118-0012  Troubleshooting Audio      sarah_smith     192.168.1.101      2025-01-19 10:25:33
```

### Key Features:
- **Read-only** - Cannot add or edit views manually
- **Date hierarchy** - Filter by day/month/year
- **Click article** to go to article admin
- **Anonymous users** shown in gray text
- Used for analytics and tracking popular articles

---

## 5. KB Article Ratings Admin

**Access**: Django Admin → CRM_APP → KB Article Ratings

### List View Features:
```
ARTICLE #         ARTICLE                    USER         VOTE                      CREATED AT
KB-20251119-0001  How to Reset Password      john_doe     [👍 Helpful]              2025-01-19 10:30:45
KB-20251119-0002  Payment Methods Guide      sarah_smith  [👎 Not Helpful]          2025-01-19 10:28:12
KB-20251118-0012  Troubleshooting Audio      mike_jones   [👍 Helpful]              2025-01-19 10:25:33
```

### Vote Badges:
- **Green badge** [👍 Helpful] - User found article helpful
- **Red badge** [👎 Not Helpful] - User did not find it helpful

### Key Features:
- **Read-only** - Cannot add or edit ratings manually
- **Date hierarchy** - Filter by day/month/year
- **One vote per user** per article
- Updates article's helpful_count and not_helpful_count automatically

---

## 6. KB Article Relations Admin

**Access**: Django Admin → CRM_APP → KB Article Relations

### List View Features:
```
FROM ARTICLE      RELATION TYPE          TO ARTICLE            DISPLAY ORDER
KB-20251119-0001  [Related]              KB-20251119-0005      0
KB-20251119-0001  [Prerequisite]         KB-20251118-0012      10
KB-20251119-0002  [See Also]             KB-20251119-0003      0
```

### Relation Type Badges:
- **Blue** [Related] - General related article
- **Purple** [See Also] - Additional reading
- **Orange** [Prerequisite] - Must read this first

### Key Features:
- **Autocomplete** for article selection (type to search)
- **Display order** controls sort order
- **One-way relations** - create reverse if needed

---

## 7. KB Article Attachments Admin

**Access**: Django Admin → CRM_APP → KB Article Attachments

### List View Features:
```
FILENAME              ARTICLE #         FILE SIZE    TYPE        UPLOADED BY    UPLOADED AT
user-guide.pdf        KB-20251119-0001  2.50 MB      [PDF]       admin          2025-01-19 10:30:45
screenshot.png        KB-20251119-0002  450.23 KB    [PNG]       john_doe       2025-01-19 10:28:12
billing-setup.xlsx    KB-20251119-0003  1.20 MB      [XLSX]      sarah_smith    2025-01-19 10:25:33
```

### File Type Badges (Color-Coded):
- **Red** [PDF] - PDF documents
- **Blue** [DOC/DOCX] - Word documents
- **Green** [XLS/XLSX] - Excel spreadsheets
- **Orange** [JPG/PNG/GIF] - Images
- **Purple** [ZIP/RAR] - Archives
- **Gray** [Other] - Other file types

### Key Features:
- **Human-readable file sizes** (bytes → KB → MB → GB)
- **Auto-filled uploaded_by** from current user
- **Date hierarchy** for filtering

---

## 8. Ticket KB Article Links Admin

**Access**: Django Admin → CRM_APP → Ticket KB Article Links

### List View Features:
```
TICKET            KB ARTICLE           LINKED BY      HELPFUL?                   LINKED AT
TKT-20251119-001  KB-20251119-0001     john_doe       [✓ Helpful]                2025-01-19 10:30:45
TKT-20251119-002  KB-20251119-0002     sarah_smith    [✗ Not Helpful]            2025-01-19 10:28:12
TKT-20251118-015  KB-20251118-0012     admin          [Not rated]                2025-01-19 10:25:33
```

### Helpful Badges:
- **Green** [✓ Helpful] - Article helped resolve ticket
- **Red** [✗ Not Helpful] - Article was not helpful
- **Gray** [Not rated] - Helpfulness not yet rated

### Key Features:
- **Autocomplete** for ticket and article selection
- **Auto-filled linked_by** from current user
- **Click ticket/article** to go to their admin pages
- **Optional feedback** - can be set later
- Used to track which articles help resolve tickets

---

## Common Admin Features Across All Interfaces

### Search Functionality
All admins have powerful search:
- **Articles**: Search by article number, title, content, excerpt
- **Categories**: Search by name, description, slug
- **Tags**: Search by name, slug
- **Views/Ratings**: Search by article number, title, username
- **Relations**: Search by both article titles and numbers
- **Attachments**: Search by filename, article number
- **Ticket Links**: Search by ticket number, article number

### Filters (Sidebar)
- **Status/Type filters** for quick access
- **Date filters** (Today, Past 7 days, This month, This year)
- **Category/Tag filters** for articles
- **User filters** for analytics

### Date Hierarchies
Analytics interfaces include date hierarchies:
- Views, Ratings, Attachments, Ticket Links
- Click year → month → day for detailed analysis

### Performance Optimizations
All list views are optimized:
- **25-50 items per page** (configurable)
- **Optimized queries** using select_related/prefetch_related
- **Fast loading** even with thousands of records

---

## Workflow Examples

### Example 1: Creating a New KB Article

1. Go to **KB Articles** → **Add KB Article**
2. Fill in:
   - Title: "How to Reset Your Password"
   - Category: Select "Account Management"
   - Tags: Check "urgent", "account", "password"
   - Content: Write article content (HTML supported)
3. Leave Status as "Draft" while working
4. **Add Attachments** (optional):
   - Click "Add another Attachment" in inline section
   - Upload PDF guide or screenshots
5. **Add Related Articles** (optional):
   - Type article number or title in autocomplete field
   - Select relation type (Related/See Also/Prerequisite)
6. **Save and continue editing** to review
7. When ready to publish:
   - Change Status to "Published"
   - Published_at is auto-filled
   - Article number is auto-generated (KB-YYYYMMDD-NNNN)
8. **Mark as Featured** (optional):
   - Check "Featured" box to show on KB homepage

### Example 2: Bulk Publishing Draft Articles

1. Go to **KB Articles** list
2. Filter by Status = "Draft"
3. Select articles using checkboxes
4. Choose Action: "Publish selected articles"
5. Click "Go"
6. Success message appears with count

### Example 3: Analyzing Article Performance

1. Go to **KB Articles** list
2. Sort by "Views" (descending) to see most viewed
3. Check "Helpfulness" column:
   - Green badges (>70%) = Great articles
   - Red badges (<40%) = Need improvement
4. Click article to see details
5. Check **Statistics** section for exact counts
6. Go to **KB Article Views** to see view history
7. Go to **KB Article Ratings** to see individual votes

### Example 4: Linking Article to Support Ticket

1. Go to **Ticket KB Article Links** → **Add Link**
2. Search for ticket using autocomplete
3. Search for article using autocomplete
4. Save (linked_by is auto-filled)
5. Later, update "Helpful?" field:
   - Yes = Article helped resolve ticket
   - No = Article was not helpful
   - (Optional - can be left as "Not rated")

---

## Tips and Best Practices

### Content Creation
- **Start with Draft status** - Review before publishing
- **Use categories** for organization - Create parent/child hierarchy
- **Tag liberally** - Makes articles easier to find
- **Add excerpts** - Or let system auto-generate from content
- **Include attachments** - Screenshots, guides, templates
- **Link related articles** - Help users find additional info

### Publishing Strategy
- **Review helpfulness** - Update articles with <70% ratings
- **Feature your best** - Put high-rated articles on homepage
- **Archive outdated** - Don't delete, just archive
- **Monitor views** - Track which articles are popular
- **Check ratings** - See what users find helpful

### Organization
- **Use consistent naming** - "How to...", "Troubleshooting...", "Guide to..."
- **Logical categories** - Account, Billing, Technical, etc.
- **Color-code tags** - Visual organization
- **Set display order** - Control category sorting
- **Add icons** - Make categories visually distinct

### Analytics
- **Track views** - See what users are reading
- **Monitor ratings** - Identify articles needing updates
- **Link to tickets** - See which articles resolve issues
- **Export to CSV** - Analyze data in Excel

---

## Quick Reference

### Auto-Generated Fields
- **article_number**: KB-YYYYMMDD-NNNN (on save)
- **slug**: from-title-like-this (on save)
- **author**: Current user (on create)
- **uploaded_by**: Current user (on attachment upload)
- **linked_by**: Current user (on ticket link)
- **published_at**: Current time (when status changes to Published)

### Color Codes
- **Status**: Green=Published, Orange=Draft, Gray=Archived
- **Visibility**: Blue=Public, Purple=Internal
- **Helpfulness**: Green>70%, Yellow 40-70%, Red<40%
- **File Types**: Red=PDF, Blue=DOC, Green=XLS, Orange=Images, Purple=Archives

### Keyboard Shortcuts
- **Ctrl+S** / **Cmd+S**: Save
- **Ctrl+Shift+S** / **Cmd+Shift+S**: Save and continue editing
- **Escape**: Close inline editor

---

## Troubleshooting

### "Cannot add article attachment"
- Check file size (may have upload limit)
- Verify MEDIA_ROOT is configured
- Ensure file permissions are correct

### "Related article autocomplete not working"
- Make sure article has a title
- Try searching by article number instead
- Check if article exists in database

### "Helpfulness percentage not showing"
- Article needs at least one vote
- Ratings are tracked in KB Article Ratings
- Percentage updates automatically via signals

### "Cannot publish article"
- Check required fields (title, category, content)
- Verify user has publish permissions
- Make sure slug is unique

---

This visual guide shows all the features available in the KB admin interface. The interface is now production-ready and follows all BMAsia CRM design patterns.
