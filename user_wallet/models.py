from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Wallet(models.Model) :
    """
    Modelo para armazenar informações de carteiras Bitcoin
    """
    WALLET_TYPES = (
        ('standard', 'Standard'),
        ('watch-only', 'Watch-Only'),
    )
    
    name = models.CharField(max_length=100)
    wallet_type = models.CharField(max_length=20, choices=WALLET_TYPES)
    xpub = models.CharField(max_length=200, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.wallet_type})"

class Address(models.Model):
    """
    Modelo para armazenar endereços Bitcoin derivados
    """
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='addresses')
    address = models.CharField(max_length=100)
    path = models.CharField(max_length=50)  # Caminho de derivação (ex: m/0/0)
    is_change = models.BooleanField(default=False)  # True para endereço de troco, False para recebimento
    index = models.IntegerField()  # Índice do endereço
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('wallet', 'path')
    
    def __str__(self):
        return f"{self.address} ({self.path})"

class Transaction(models.Model):
    """
    Modelo para armazenar transações Bitcoin
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
    )
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    txid = models.CharField(max_length=100)
    amount = models.BigIntegerField()  # Valor em satoshis
    fee = models.BigIntegerField()  # Taxa em satoshis
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.txid} ({self.status})"

class BitcoinPriceCache(models.Model):
    price = models.FloatField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    change24h = models.FloatField(default=0)
    low24h = models.FloatField(default=0)
    high24h = models.FloatField(default=0)

    @classmethod
    def get_cached_price(cls):
        instance, created = cls.objects.get_or_create(
            id=1,
            defaults={'price': 0}
        )
        return instance

    class Meta:
        verbose_name = "Bitcoin Price Cache"
        verbose_name_plural = "Bitcoin Price Caches"