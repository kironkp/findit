from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=20, default='#1F3A3D')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tag-index')


class Location(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    is_person = models.BooleanField(
        default=False,
        help_text='Check if this represents a person you lent something to.',
    )
    icon = models.CharField(max_length=40, blank=True, default='')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('location-detail', kwargs={'pk': self.id})

    def breadcrumb(self):
        parts = [self.name]
        node = self.parent
        seen = {self.id}
        while node and node.id not in seen:
            seen.add(node.id)
            parts.append(node.name)
            node = node.parent
        return ' › '.join(reversed(parts))


class Item(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    distinguishing_detail = models.CharField(
        max_length=200,
        blank=True,
        help_text='Anything that sets it apart from a similar item (e.g. "cracked corner").',
    )
    quantity = models.PositiveIntegerField(default=1)
    photo = models.ImageField(upload_to='items/', blank=True, null=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='items')
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
    )
    archived = models.BooleanField(default=False)
    last_confirmed = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('item-detail', kwargs={'pk': self.id})


class LocationLog(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='location_logs')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    return_by = models.DateField(
        null=True,
        blank=True,
        help_text='Optional return date (useful when lending to a person).',
    )
    moved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-moved_at']

    def __str__(self):
        where = self.location.name if self.location else 'unknown'
        return f'{self.item.name} → {where} on {self.moved_at:%Y-%m-%d}'
