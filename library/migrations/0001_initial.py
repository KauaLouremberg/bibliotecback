import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryBook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('author', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('cover_url', models.URLField(blank=True)),
                ('has_physical_copy', models.BooleanField(default=False)),
                ('sharing_status', models.CharField(choices=[('private', 'Privado'), ('showcase', 'Exibir no perfil'), ('loan', 'Disponível para empréstimo'), ('exchange', 'Disponível para troca'), ('donation', 'Disponível para doação')], default='private', max_length=24)),
                ('location_label', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_books', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at', '-created_at', 'title'],
            },
        ),
        migrations.CreateModel(
            name='SocialPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intent', models.CharField(choices=[('need', 'Procuro este livro'), ('donation', 'Estou doando'), ('exchange', 'Quero trocar'), ('loan', 'Posso emprestar'), ('offer', 'Tenho este livro disponível')], max_length=24)),
                ('book_title', models.CharField(max_length=255)),
                ('book_author', models.CharField(max_length=255)),
                ('caption', models.TextField(blank=True)),
                ('location_label', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('inventory_book', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='social_posts', to='library.inventorybook')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_posts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-updated_at'],
            },
        ),
    ]
