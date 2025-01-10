# Generated by Django 5.1.3 on 2025-01-10 17:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_alter_user_work_end_time_alter_user_work_start_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='product_weight',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='sale',
            name='quantity',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
