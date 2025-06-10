from rest_framework import permissions
from django.db.models import Q


class RoleBasedPermission(permissions.BasePermission):
    """
    Custom permission class that checks user roles and field-level permissions
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin users have full access
        if request.user.role == 'Admin':
            return True
        
        # Define role-based access for different views
        view_permissions = {
            'CompanyViewSet': ['Sales', 'Finance', 'Tech', 'Music', 'Admin'],
            'ContactViewSet': ['Sales', 'Finance', 'Tech', 'Music', 'Admin'],
            'NoteViewSet': ['Sales', 'Finance', 'Tech', 'Music', 'Admin'],
            'TaskViewSet': ['Sales', 'Finance', 'Tech', 'Music', 'Admin'],
            'OpportunityViewSet': ['Sales', 'Admin'],
            'OpportunityActivityViewSet': ['Sales', 'Admin'],
            'ContractViewSet': ['Finance', 'Admin'],
            'InvoiceViewSet': ['Finance', 'Admin'],
            'AuditLogViewSet': ['Admin'],
        }
        
        view_name = view.__class__.__name__
        allowed_roles = view_permissions.get(view_name, [])
        
        return request.user.role in allowed_roles
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # Admin users have full access
        if request.user.role == 'Admin':
            return True
        
        # Sales users can only access their own opportunities
        if view.__class__.__name__ in ['OpportunityViewSet', 'OpportunityActivityViewSet']:
            if request.user.role == 'Sales':
                if hasattr(obj, 'owner'):
                    return obj.owner == request.user
                elif hasattr(obj, 'opportunity'):
                    return obj.opportunity.owner == request.user
        
        # Finance users have full access to contracts and invoices
        if view.__class__.__name__ in ['ContractViewSet', 'InvoiceViewSet']:
            return request.user.role == 'Finance'
        
        # For other objects, check general role permissions
        return self.has_permission(request, view)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'author'):
            return obj.author == request.user
        elif hasattr(obj, 'assigned_to'):
            return obj.assigned_to == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class DepartmentPermission(permissions.BasePermission):
    """
    Permission class that restricts access based on department/role
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Define department-specific restrictions
        department_restrictions = {
            'Sales': {
                'read': ['Company', 'Contact', 'Note', 'Task', 'Opportunity', 'OpportunityActivity'],
                'write': ['Company', 'Contact', 'Note', 'Task', 'Opportunity', 'OpportunityActivity'],
                'delete': ['Note', 'Task', 'OpportunityActivity']
            },
            'Finance': {
                'read': ['Company', 'Contact', 'Contract', 'Invoice', 'Opportunity'],
                'write': ['Contract', 'Invoice'],
                'delete': ['Invoice']
            },
            'Tech': {
                'read': ['Company', 'Contact', 'Note', 'Task'],
                'write': ['Note', 'Task'],
                'delete': ['Note', 'Task']
            },
            'Music': {
                'read': ['Company', 'Contact', 'Note', 'Task'],
                'write': ['Note', 'Task'],
                'delete': ['Note', 'Task']
            },
            'Admin': {
                'read': '*',
                'write': '*',
                'delete': '*'
            }
        }
        
        user_role = request.user.role
        if user_role not in department_restrictions:
            return False
        
        permissions_for_role = department_restrictions[user_role]
        
        # Extract model name from view
        model_name = getattr(view, 'model', None)
        if model_name:
            model_name = model_name.__name__
        else:
            # Try to extract from viewset name
            view_name = view.__class__.__name__
            model_name = view_name.replace('ViewSet', '')
        
        # Check permissions based on HTTP method
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            allowed_models = permissions_for_role.get('read', [])
        elif request.method in ['POST', 'PUT', 'PATCH']:
            allowed_models = permissions_for_role.get('write', [])
        elif request.method == 'DELETE':
            allowed_models = permissions_for_role.get('delete', [])
        else:
            return False
        
        # Admin has access to everything
        if allowed_models == '*':
            return True
        
        return model_name in allowed_models


class ReadOnlyForNonOwner(permissions.BasePermission):
    """
    Permission that allows read-only access for non-owners
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin always has full access
        if request.user.role == 'Admin':
            return True
        
        # Read permissions for everyone with basic access
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for owners
        owner_fields = ['owner', 'author', 'assigned_to', 'created_by']
        for field in owner_fields:
            if hasattr(obj, field):
                owner = getattr(obj, field)
                if owner == request.user:
                    return True
        
        return False


class TaskAssigneePermission(permissions.BasePermission):
    """
    Custom permission for task management - assignees can edit their tasks
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.role == 'Admin':
            return True
        
        # Read access for anyone in the system
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write access for assignee, creator, or same department
        if hasattr(obj, 'assigned_to') and obj.assigned_to == request.user:
            return True
        
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        if hasattr(obj, 'department') and obj.department == request.user.role:
            return True
        
        return False


class CompanyAccessPermission(permissions.BasePermission):
    """
    Permission for company access based on opportunities owned
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.role == 'Admin':
            return True
        
        # Read access for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Sales users can edit companies they have opportunities for
        if request.user.role == 'Sales':
            return obj.opportunities.filter(owner=request.user).exists()
        
        # Finance users can edit companies with contracts
        if request.user.role == 'Finance':
            return obj.contracts.exists()
        
        # Tech and Music can edit if they have tasks for this company
        if request.user.role in ['Tech', 'Music']:
            return obj.tasks.filter(
                Q(assigned_to=request.user) | Q(department=request.user.role)
            ).exists()
        
        return False