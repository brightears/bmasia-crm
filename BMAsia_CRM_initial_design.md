# BMAsia CRM – Initial Design and Implementation Plan

**Project Goal:** Develop a lightweight, web‑accessible CRM for BMAsia that supports Sales, Finance, Tech Support, and Music Design workflows. The system will be built with a robust backend (Python/Django in this design) and a modern frontend (React), following best practices for scalability, usability, and security.

---

## Database Schema Design

The database uses a relational schema (PostgreSQL in production; SQLite can be used for dev) to organize clients, sales funnel data, and finance records. We define models for each main module: **Client Database**, **Sales Funnel**, and **Finance**. An audit log and task system are included to track changes and inter‑department tasks.

### 1. Client Database Module

Stores client companies, their contacts, notes, and tasks.

```python
# models.py – Client Database

from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Sales', 'Sales'),
        ('Finance', 'Finance'),
        ('Tech', 'Tech Support'),
        ('Music', 'Music Design'),
        ('Admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Sales')

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    zone = models.CharField(max_length=100, blank=True)
    current_plan = models.CharField(max_length=100, blank=True)

class Contact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=50, blank=True)

class Note(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notes')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    department = models.CharField(max_length=20, choices=User.ROLE_CHOICES, blank=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=50)
    record_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(null=True, blank=True)
```

### 2. Sales Funnel Module

Tracks each opportunity’s stage and follow‑up data.

```python
# models.py – Sales Funnel

class Opportunity(models.Model):
    STAGE_CHOICES = [
        ('Lead', 'Lead'),
        ('Contacted', 'Contacted'),
        ('Proposal', 'Proposal Sent'),
        ('Negotiation', 'Negotiation'),
        ('Closed Won', 'Closed - Won'),
        ('Closed Lost', 'Closed - Lost'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField(max_length=255)
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Lead')
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='opportunities')
    last_contact_date = models.DateField(null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
```

### 3. Finance Module

Manages contracts and invoices; enables renewal alerts.

```python
# models.py – Finance

class Contract(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='contracts')
    start_date = models.DateField()
    end_date = models.DateField()
    value = models.DecimalField(max_digits=12, decimal_places=2)
    auto_renew = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

class Invoice(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50)
    issue_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
```

---

## Role‑Based Authentication & Authorization

Use Django’s auth system with a `role` field on the `User` model. Protect views with decorators:

```python
# auth.py – role helper
from django.http import HttpResponseForbidden

def role_required(allowed_roles):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Login required.")
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden("Permission denied.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
```

---

## Basic Web UI (React)

### Client List

```jsx
// ClientList.jsx
function ClientList() {
  const [clients, setClients] = React.useState([]);
  React.useEffect(() => {
    fetch('/api/companies/')
      .then(r => r.json())
      .then(setClients);
  }, []);
  return (
    <ul>
      {clients.map(c => (
        <li key={c.id}>
          <strong>{c.name}</strong> – {c.zone}
          <button onClick={() => window.location.href = `/clients/${c.id}`}>View</button>
        </li>
      ))}
    </ul>
  );
}
```

### Client Detail / Edit

```jsx
// ClientDetail.jsx
function ClientDetail({ clientId }) {
  const [client, setClient] = React.useState(null);
  const [form, setForm] = React.useState({});
  const [edit, setEdit] = React.useState(false);

  React.useEffect(() => {
    fetch(`/api/companies/${clientId}/`).then(r => r.json()).then(data => {
      setClient(data);
      setForm({ name: data.name, zone: data.zone || '', current_plan: data.current_plan || '' });
    });
  }, [clientId]);

  const update = () => {
    fetch(`/api/companies/${clientId}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    }).then(r => r.json()).then(setClient).finally(() => setEdit(false));
  };

  if (!client) return <p>Loading…</p>;

  return edit ? (
    <div>
      <input value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
      {/* …other fields… */}
      <button onClick={update}>Save</button>
    </div>
  ) : (
    <div>
      <h2>{client.name}</h2>
      {/* …display info… */}
      <button onClick={()=>setEdit(true)}>Edit</button>
    </div>
  );
}
```

---

## Setup & Deployment

### Backend (Django)

```bash
python -m venv env && source env/bin/activate
pip install django djangorestframework psycopg2-binary
django-admin startproject bmasia_crm .
django-admin startapp crm_app
# add crm_app to INSTALLED_APPS & set AUTH_USER_MODEL
python manage.py makemigrations && python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend (React)

```bash
npx create-react-app bmasia-crm-frontend
cd bmasia-crm-frontend && npm start
```

Ensure CORS or proxy config for API calls.

### Production Considerations

* Deploy Django via Gunicorn/Uvicorn behind NGINX.
* Use PostgreSQL in production; keep backups.
* Serve React build as static files or deploy separately.
* Enforce HTTPS and environment variables for secrets.
* Schedule daily job (Celery beat or cron) for renewal and follow‑up alerts.

---

## Next Development Steps

1. **Finish REST endpoints** with DRF viewsets + auth.
2. **Implement granular permissions** for each role.
3. **Enhance UI** with forms, dashboards, and responsive design.
4. **Notifications & AI reminders** (optional) via scheduled jobs.
5. **Google Sheets import/export** if needed.
6. **Comprehensive tests** (unit + integration).
7. **Documentation & training** for each department.
8. **Production deployment & monitoring**.

---

> **Optional AI Integration:**  
> Keep GPT/Claude usage behind a toggle to control cost. Examples: summarizing notes, drafting follow‑ups, renewal reminders.

---

**End of file**
