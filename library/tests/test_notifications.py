from django.test import TestCase

from accounts.models import User
from library.models import LibraryNotification
from library.notification_services import _truncate, notify


class NotificationTruncateTests(TestCase):
    def test_truncate_short_text_unchanged(self):
        self.assertEqual(_truncate("abc", 500), "abc")

    def test_truncate_long_text(self):
        text = "x" * 600
        result = _truncate(text, 500)
        self.assertLessEqual(len(result), 500)
        self.assertTrue(result.endswith("…"))

    def test_notify_truncates_body(self):
        recipient = User.objects.create_user(email="owner@example.com", password="secret123")
        actor = User.objects.create_user(email="requester@example.com", password="secret123")

        long_title = "T" * 400
        notify(
            recipient_id=recipient.pk,
            kind="trade_completed",
            title="Negociação concluída",
            body=f"{actor.email} marcou «{long_title}» como concluída.",
            actor_id=actor.pk,
            trade_id=1,
        )

        created = LibraryNotification.objects.get(recipient=recipient)
        self.assertLessEqual(len(created.body), 500)
