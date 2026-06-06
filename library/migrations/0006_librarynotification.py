from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("library", "0005_signalchatthread_signalchatmessage_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("chat_started", "Chat iniciado"),
                            ("chat_message", "Mensagem de chat"),
                            ("trade_received", "Proposta recebida"),
                            ("trade_accepted", "Proposta aceita"),
                            ("trade_rejected", "Proposta recusada"),
                            ("trade_completed", "Negociação concluída"),
                        ],
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("body", models.CharField(max_length=500)),
                ("thread_id", models.PositiveIntegerField(blank=True, null=True)),
                ("trade_id", models.PositiveIntegerField(blank=True, null=True)),
                ("post_id", models.PositiveIntegerField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_notifications_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
