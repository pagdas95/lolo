# Generated by Django 5.0.9 on 2024-10-28 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tickets',
            field=models.PositiveIntegerField(default=0, verbose_name='Tickets'),
        ),
    ]
