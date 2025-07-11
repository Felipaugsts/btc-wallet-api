# Generated by Django 4.1.7 on 2025-04-27 01:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_wallet', '0002_bitcoinpricecache'),
    ]

    operations = [
        migrations.AddField(
            model_name='bitcoinpricecache',
            name='change24h',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='bitcoinpricecache',
            name='high24h',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='bitcoinpricecache',
            name='low24h',
            field=models.FloatField(default=0),
        ),
    ]
