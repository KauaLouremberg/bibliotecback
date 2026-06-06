from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from library.models import InventoryBook, LibraryNotification, TradeRequest


class TradeStatusApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(email="owner@example.com", password="secret123", full_name="Owner")
        self.requester = User.objects.create_user(
            email="requester@example.com",
            password="secret123",
            full_name="Requester",
        )
        token = str(AccessToken.for_user(self.requester))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.book = InventoryBook.objects.create(
            owner=self.owner,
            title="A" * 255,
            author="Autor",
            sharing_status=InventoryBook.SharingStatus.EXCHANGE,
        )
        self.trade = TradeRequest.objects.create(
            requester=self.requester,
            owner=self.owner,
            book_requested=self.book,
            status=TradeRequest.Status.ACCEPTED,
        )

    def test_complete_trade_with_long_title_does_not_500(self):
        response = self.client.patch(
            f"/api/library/trades/{self.trade.pk}/status",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.trade.refresh_from_db()
        self.assertEqual(self.trade.status, TradeRequest.Status.COMPLETED)
        self.assertEqual(LibraryNotification.objects.filter(trade_id=self.trade.pk).count(), 1)
