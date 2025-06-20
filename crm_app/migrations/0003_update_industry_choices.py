# Generated by Django 5.2.2 on 2025-06-10 05:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0002_update_opportunity_stages'),
    ]

    operations = [
        migrations.AlterField(
            model_name='company',
            name='industry',
            field=models.CharField(blank=True, choices=[('Hotels', 'Hotels & Resorts'), ('Restaurants', 'Restaurants'), ('Bars', 'Bars & Nightlife'), ('Quick Service Restaurants', 'Quick Service Restaurants'), ('Retail Fashion', 'Retail Fashion'), ('Retail Food', 'Retail Food'), ('Malls', 'Shopping Malls'), ('Offices', 'Offices & Corporate'), ('Hospitals', 'Hospitals & Medical'), ('Spas', 'Spas & Wellness'), ('Fun Parks', 'Fun Parks & Entertainment'), ('Cafes', 'Cafes & Coffee Shops'), ('Gyms', 'Gyms & Fitness Centers'), ('Salons', 'Salons & Beauty'), ('Banks', 'Banks & Financial'), ('Other', 'Other')], max_length=50),
        ),
    ]
