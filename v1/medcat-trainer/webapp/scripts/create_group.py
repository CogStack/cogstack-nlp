from django.contrib.auth.models import Group, Permission
from itertools import chain

print("Checking for Default User Group")
group, created = Group.objects.get_or_create(name='user_group')
if created:
    print("No Default User Group Found - Creating with Permissions")
dataset = list(Permission.objects.filter(codename__contains='dataset').exclude(codename__contains='delete'))
concept = list(Permission.objects.filter(codename__contains='concept'))
project = list(Permission.objects.filter(codename__contains="projectannotateentities").exclude(codename__contains="delete"))
permissions = chain(dataset, concept, project)
for p in permissions:
    group.permissions.add(p)
print("User_group created with minimum correct permissions")