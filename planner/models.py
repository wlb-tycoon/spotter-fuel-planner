import uuid

from django.db import models


class Station(models.Model):
    opis_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=250)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=150)
    state = models.CharField(max_length=2, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=8)
    longitude = models.FloatField()
    latitude = models.FloatField()
    source = models.CharField(max_length=200)
    confidence = models.CharField(max_length=30)

    class Meta:
        indexes = [models.Index(fields=["latitude", "longitude"])]


class RoutePlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField()
