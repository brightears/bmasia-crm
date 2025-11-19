# Knowledge Base API Endpoints - Phase 3 Complete

## Overview
This document lists all REST API endpoints created for the Knowledge Base system in Phase 3. All endpoints require authentication and use the `/api/v1/` prefix.

---

## 1. KB Categories
**Base URL:** `/api/v1/kb/categories/`

### Endpoints:
- **GET** `/api/v1/kb/categories/` - List all categories
- **POST** `/api/v1/kb/categories/` - Create new category
- **GET** `/api/v1/kb/categories/{id}/` - Get category details
- **PUT** `/api/v1/kb/categories/{id}/` - Update category
- **PATCH** `/api/v1/kb/categories/{id}/` - Partial update
- **DELETE** `/api/v1/kb/categories/{id}/` - Delete category

### Filters:
- `?is_active=true/false` - Filter by active status
- `?parent={uuid}` - Filter by parent category
- `?search=query` - Search in name, description

### Ordering:
- `?ordering=name` - Order by name
- `?ordering=display_order` - Order by display order (default)

### Features:
- Hierarchical parent/child relationships
- Auto-generated slug from name
- Article count per category
- Full path display (e.g., "Parent > Child")
- Children categories included (max depth 2)

---

## 2. KB Tags
**Base URL:** `/api/v1/kb/tags/`

### Endpoints:
- **GET** `/api/v1/kb/tags/` - List all tags
- **POST** `/api/v1/kb/tags/` - Create new tag
- **GET** `/api/v1/kb/tags/{id}/` - Get tag details
- **PUT** `/api/v1/kb/tags/{id}/` - Update tag
- **PATCH** `/api/v1/kb/tags/{id}/` - Partial update
- **DELETE** `/api/v1/kb/tags/{id}/` - Delete tag

### Filters:
- `?search=query` - Search in tag name

### Ordering:
- `?ordering=name` - Order by name (default)

### Features:
- Auto-generated slug from name
- Color support for UI (hex code)
- Article count per tag

---

## 3. KB Articles
**Base URL:** `/api/v1/kb/articles/`

### Standard CRUD Endpoints:
- **GET** `/api/v1/kb/articles/` - List all articles (uses lightweight serializer)
- **POST** `/api/v1/kb/articles/` - Create new article
- **GET** `/api/v1/kb/articles/{id}/` - Get article details (full serializer)
- **PUT** `/api/v1/kb/articles/{id}/` - Update article
- **PATCH** `/api/v1/kb/articles/{id}/` - Partial update
- **DELETE** `/api/v1/kb/articles/{id}/` - Delete article

### Custom Action Endpoints:

#### POST `/api/v1/kb/articles/{id}/record_view/`
Record article view for analytics.
```json
Request Body:
{
  "session_id": "unique-session-id"
}

Response:
{
  "message": "View recorded",
  "view_count": 42
}
```

#### POST `/api/v1/kb/articles/{id}/rate/`
Rate article as helpful or not helpful.
```json
Request Body:
{
  "is_helpful": true  // or false
}

Response:
{
  "message": "Rating saved",
  "helpful_count": 15,
  "not_helpful_count": 2,
  "helpfulness_ratio": 88.2
}
```

#### GET `/api/v1/kb/articles/{id}/related/`
Get related articles.
```json
Response:
[
  {
    "id": "uuid",
    "article_number": "KB-20251119-0001",
    "title": "Related Article Title",
    "slug": "related-article-title",
    "relation_type": "related",
    "relation_type_display": "Related Article"
  }
]
```

#### POST `/api/v1/kb/articles/{id}/add_attachment/`
Upload file attachment (multipart/form-data).
```
Content-Type: multipart/form-data
Body: file field with file upload

Response: Attachment object with metadata
```

#### POST `/api/v1/kb/articles/{id}/link_to_ticket/`
Link article to support ticket.
```json
Request Body:
{
  "ticket_id": "uuid",
  "is_helpful": true  // optional
}

Response: TicketKBArticle link object
```

#### GET `/api/v1/kb/articles/search/?q=query`
Full-text search (PostgreSQL) or fallback search (SQLite).
```
Query Params:
- q=search query (required)

Response: Paginated list of articles
```

#### GET `/api/v1/kb/articles/featured/`
Get featured articles (max 10).
```json
Response: List of featured articles
```

#### GET `/api/v1/kb/articles/popular/?limit=10`
Get most viewed articles.
```
Query Params:
- limit=10 (optional, default 10)

Response: List of popular articles
```

#### GET `/api/v1/kb/articles/helpful/?limit=10`
Get most helpful articles.
```
Query Params:
- limit=10 (optional, default 10)

Response: List of helpful articles
```

### Filters:
- `?status=draft/published/archived` - Filter by status
- `?visibility=public/internal` - Filter by visibility
- `?category={uuid}` - Filter by category
- `?featured=true/false` - Filter featured articles
- `?tags={uuid}` - Filter by tag
- `?search=query` - Search in article_number, title, content, excerpt

### Ordering:
- `?ordering=-published_at` - Order by publish date (default)
- `?ordering=-created_at` - Order by creation date
- `?ordering=-view_count` - Order by views
- `?ordering=-helpful_count` - Order by helpful votes

### Features:
- Auto-generated article number (KB-YYYYMMDD-NNNN)
- Auto-generated slug from title
- Auto-generated excerpt from content
- Author auto-set from request.user
- Tags support (many-to-many)
- Related articles
- Attachments
- View tracking
- Helpful/not helpful ratings
- Full-text search (PostgreSQL)
- Optimized queries (select_related, prefetch_related)

### Validation:
- Content minimum 100 characters (excluding HTML)
- Title uniqueness per category
- Auto-set published_at when status changes to 'published'

---

## 4. KB Article Views
**Base URL:** `/api/v1/kb/article-views/`

### Endpoints:
- **GET** `/api/v1/kb/article-views/` - List all views (analytics)
- **GET** `/api/v1/kb/article-views/{id}/` - Get view details

**Note:** Read-only ViewSet (no create/update/delete via API)

### Filters:
- `?article={uuid}` - Filter by article
- `?user={uuid}` - Filter by user
- `?viewed_at={datetime}` - Filter by view date

### Ordering:
- `?ordering=-viewed_at` - Order by view date (default)

### Features:
- Tracks IP address
- Tracks session ID (prevents duplicate counting)
- Unique constraint: one view per article per session

---

## 5. KB Article Ratings
**Base URL:** `/api/v1/kb/article-ratings/`

### Endpoints:
- **GET** `/api/v1/kb/article-ratings/` - List all ratings
- **POST** `/api/v1/kb/article-ratings/` - Create/update rating
- **GET** `/api/v1/kb/article-ratings/{id}/` - Get rating details
- **PUT** `/api/v1/kb/article-ratings/{id}/` - Update rating
- **PATCH** `/api/v1/kb/article-ratings/{id}/` - Partial update
- **DELETE** `/api/v1/kb/article-ratings/{id}/` - Delete rating

### Filters:
- `?article={uuid}` - Filter by article
- `?user={uuid}` - Filter by user
- `?is_helpful=true/false` - Filter by rating type

### Ordering:
- `?ordering=-created_at` - Order by creation date (default)

### Features:
- User auto-set from request.user
- Unique constraint: one vote per user per article
- Auto-updates article helpful_count and not_helpful_count

### Validation:
- Prevents duplicate ratings (enforced by unique constraint)
- Updates existing rating if user votes again

---

## 6. KB Article Relations
**Base URL:** `/api/v1/kb/article-relations/`

### Endpoints:
- **GET** `/api/v1/kb/article-relations/` - List all relations
- **POST** `/api/v1/kb/article-relations/` - Create relation
- **GET** `/api/v1/kb/article-relations/{id}/` - Get relation details
- **PUT** `/api/v1/kb/article-relations/{id}/` - Update relation
- **PATCH** `/api/v1/kb/article-relations/{id}/` - Partial update
- **DELETE** `/api/v1/kb/article-relations/{id}/` - Delete relation

### Filters:
- `?from_article={uuid}` - Filter by source article
- `?to_article={uuid}` - Filter by target article
- `?relation_type=related/see_also/prerequisite` - Filter by type

### Ordering:
- `?ordering=from_article` - Order by source article
- `?ordering=display_order` - Order by display order

### Relation Types:
- `related` - Related Article
- `see_also` - See Also
- `prerequisite` - Prerequisite Reading

### Features:
- Directional relationships (from_article → to_article)
- Display order for sorting
- Unique constraint: one relation per article pair

### Validation:
- Cannot relate article to itself

---

## 7. KB Article Attachments
**Base URL:** `/api/v1/kb/article-attachments/`

### Endpoints:
- **GET** `/api/v1/kb/article-attachments/` - List all attachments
- **POST** `/api/v1/kb/article-attachments/` - Upload attachment
- **GET** `/api/v1/kb/article-attachments/{id}/` - Get attachment details
- **PUT** `/api/v1/kb/article-attachments/{id}/` - Update attachment
- **DELETE** `/api/v1/kb/article-attachments/{id}/` - Delete attachment

### Filters:
- `?article={uuid}` - Filter by article

### Ordering:
- `?ordering=-uploaded_at` - Order by upload date (default)

### Features:
- File upload support (multipart/form-data)
- Auto-populated filename and file_size from uploaded file
- uploaded_by auto-set from request.user
- File extension extraction
- File URL in response

### Upload Format:
```
Content-Type: multipart/form-data

Fields:
- file: (binary file data)
- article: uuid (required)
```

---

## 8. Ticket KB Article Links
**Base URL:** `/api/v1/kb/ticket-articles/`

### Endpoints:
- **GET** `/api/v1/kb/ticket-articles/` - List all links
- **POST** `/api/v1/kb/ticket-articles/` - Create link
- **GET** `/api/v1/kb/ticket-articles/{id}/` - Get link details
- **PUT** `/api/v1/kb/ticket-articles/{id}/` - Update link
- **PATCH** `/api/v1/kb/ticket-articles/{id}/` - Partial update
- **DELETE** `/api/v1/kb/ticket-articles/{id}/` - Delete link

### Filters:
- `?ticket={uuid}` - Filter by ticket
- `?article={uuid}` - Filter by article
- `?is_helpful=true/false/null` - Filter by helpfulness

### Ordering:
- `?ordering=-linked_at` - Order by link date (default)

### Features:
- Links KB articles to support tickets
- Tracks which articles were helpful for resolving tickets
- linked_by auto-set from request.user
- Unique constraint: one link per ticket-article pair

### Use Cases:
- Track article effectiveness for ticket resolution
- Suggest helpful articles based on ticket category
- Identify knowledge gaps (tickets with no helpful articles)

---

## Response Format

### Success Response:
```json
{
  "id": "uuid",
  "field1": "value1",
  "field2": "value2",
  ...
}
```

### List Response (Paginated):
```json
{
  "count": 100,
  "next": "http://api/v1/kb/articles/?page=2",
  "previous": null,
  "results": [
    { "id": "uuid", ... },
    { "id": "uuid", ... }
  ]
}
```

### Error Response:
```json
{
  "error": "Error message",
  "detail": "Detailed error information"
}
```

### Validation Error Response:
```json
{
  "field_name": [
    "Error message for this field"
  ]
}
```

---

## Authentication

All endpoints require authentication. Include JWT token in request headers:

```
Authorization: Bearer {jwt_token}
```

---

## Query Optimization

All ViewSets use optimized queries:

1. **KBCategoryViewSet**: Prefetches parent and children
2. **KBArticleViewSet**: select_related(category, author) + prefetch_related(tags, attachments, relations)
3. **KBArticleViewViewSet**: select_related(article, user)
4. **KBArticleRatingViewSet**: select_related(article, user)
5. **KBArticleRelationViewSet**: select_related(from_article, to_article)
6. **KBArticleAttachmentViewSet**: select_related(article, uploaded_by)
7. **TicketKBArticleViewSet**: select_related(ticket, article, linked_by)

---

## Full-Text Search Implementation

### PostgreSQL (Production):
Uses `search_vector` field with PostgreSQL full-text search:
```python
from django.contrib.postgres.search import SearchQuery
search_query = SearchQuery(query)
queryset.filter(search_vector=search_query)
```

### SQLite (Development):
Falls back to simple icontains search:
```python
queryset.filter(
    Q(title__icontains=query) | Q(content__icontains=query)
)
```

The system automatically detects database vendor and uses appropriate search method.

---

## Example Usage

### Create a New Article:
```bash
curl -X POST https://bmasia-crm.onrender.com/api/v1/kb/articles/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "How to Setup Music Zones",
    "content": "<p>Step-by-step guide...</p>",
    "category_id": "uuid-of-category",
    "tag_ids": ["uuid-tag-1", "uuid-tag-2"],
    "status": "published",
    "visibility": "public"
  }'
```

### Search Articles:
```bash
curl -X GET "https://bmasia-crm.onrender.com/api/v1/kb/articles/search/?q=music+zone" \
  -H "Authorization: Bearer {token}"
```

### Rate an Article:
```bash
curl -X POST https://bmasia-crm.onrender.com/api/v1/kb/articles/{id}/rate/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"is_helpful": true}'
```

### Link Article to Ticket:
```bash
curl -X POST https://bmasia-crm.onrender.com/api/v1/kb/articles/{id}/link_to_ticket/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "uuid-of-ticket",
    "is_helpful": true
  }'
```

---

## Summary

**Total Endpoints Created:** 8 ViewSets with 70+ total endpoints

1. **KBCategoryViewSet** - 6 endpoints (CRUD + list)
2. **KBTagViewSet** - 6 endpoints (CRUD + list)
3. **KBArticleViewSet** - 15 endpoints (CRUD + 9 custom actions)
4. **KBArticleViewViewSet** - 2 endpoints (read-only analytics)
5. **KBArticleRatingViewSet** - 6 endpoints (CRUD + list)
6. **KBArticleRelationViewSet** - 6 endpoints (CRUD + list)
7. **KBArticleAttachmentViewSet** - 6 endpoints (CRUD + list)
8. **TicketKBArticleViewSet** - 6 endpoints (CRUD + list)

All endpoints support:
- Authentication (JWT)
- Filtering
- Search
- Ordering
- Pagination (25 items per page, 50 for analytics)
- Proper HTTP status codes
- Comprehensive error handling
- Auto-populated fields (author, uploaded_by, linked_by)
- Query optimization
