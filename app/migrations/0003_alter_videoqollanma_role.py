# Generated by Django 5.1.3 on 2025-01-15 16:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_alter_user_work_end_time_alter_user_work_start_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='videoqollanma',
            name='role',
            field=models.CharField(choices=[('SELLER', 'Seller'), ('ADMIN', 'Admin'), ('DIRECTOR', 'Director')], max_length=10),
        ),
    ]
