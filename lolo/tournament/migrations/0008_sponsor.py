# Generated by Django 5.0.9 on 2025-04-19 14:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament', '0007_tournament_is_showcase'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sponsor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Sponsor name', max_length=200)),
                ('description', models.TextField(blank=True, help_text='About the sponsor')),
                ('logo', models.ImageField(help_text='Sponsor logo', upload_to='sponsor_logos/')),
                ('website_url', models.URLField(blank=True, help_text="Sponsor's website URL")),
                ('is_active', models.BooleanField(default=True, help_text='Indicates if sponsor is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tournaments', models.ManyToManyField(blank=True, help_text='Tournaments sponsored by this sponsor', related_name='sponsors', to='tournament.tournament')),
            ],
        ),
    ]
