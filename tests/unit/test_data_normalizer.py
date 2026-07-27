"""Unit tests for the Data Normalizer."""

from datetime import datetime, timezone
from decimal import Decimal

from src.monitoring.processors.data_normalizer import DataNormalizer


class TestDataNormalizer:
    """Tests for DataNormalizer."""

    def setup_method(self):
        self.normalizer = DataNormalizer()

    def test_normalize_basic_row(self):
        """Test normalizing a basic Azure cost row."""
        raw = [
            {
                "UsageDate": "2025-01-15",
                "PreTaxCost": 42.50,
                "SubscriptionId": "sub-001",
                "ResourceGroup": "rg-prod",
                "ResourceId": "/subscriptions/sub-001/resourceGroups/rg-prod/providers/Microsoft.Compute/vm-1",
                "ResourceName": "vm-1",
                "ServiceName": "Microsoft.Compute",
                "ResourceType": "Microsoft.Compute/virtualMachines",
                "ResourceLocation": "eastus",
                "Currency": "USD",
            }
        ]

        records = self.normalizer.normalize_cost_rows(raw)

        assert len(records) == 1
        rec = records[0]
        assert rec.subscription_id == "sub-001"
        assert rec.resource_group == "rg-prod"
        assert rec.resource_name == "vm-1"
        assert rec.service_name == "Microsoft.Compute"
        assert rec.cost == Decimal("42.5")
        assert rec.region == "East US"  # Resolved from alias

    def test_normalize_skips_zero_cost(self):
        """Rows with zero cost should be skipped."""
        raw = [
            {"UsageDate": "2025-01-15", "PreTaxCost": 0, "SubscriptionId": "sub-001",
             "ResourceGroup": "rg", "ResourceId": "res-1", "ResourceName": "r",
             "ServiceName": "S", "ResourceType": "T", "ResourceLocation": "eastus"},
        ]
        records = self.normalizer.normalize_cost_rows(raw)
        assert len(records) == 0

    def test_normalize_deduplication(self):
        """Duplicate rows should be deduplicated."""
        row = {
            "UsageDate": "2025-01-15",
            "PreTaxCost": 10.0,
            "SubscriptionId": "sub-001",
            "ResourceGroup": "rg",
            "ResourceId": "res-1",
            "ResourceName": "r",
            "ServiceName": "S",
            "ResourceType": "T",
            "ResourceLocation": "westus",
        }
        records = self.normalizer.normalize_cost_rows([row, row, row])
        assert len(records) == 1

    def test_normalize_column_aliases(self):
        """Test various Azure column name aliases."""
        raw = [
            {
                "usageDate": "2025-06-01",
                "CostInBillingCurrency": 99.99,
                "subscriptionId": "sub-002",
                "resourceGroup": "rg-test",
                "resourceId": "res-abc",
                "resourceName": "my-resource",
                "ConsumedService": "Microsoft.Storage",
                "resourceType": "Microsoft.Storage/storageAccounts",
                "Location": "westeurope",
                "BillingCurrency": "EUR",
            }
        ]
        records = self.normalizer.normalize_cost_rows(raw)
        assert len(records) == 1
        assert records[0].service_name == "Microsoft.Storage"
        assert records[0].currency == "EUR"
        assert records[0].region == "West Europe"

    def test_normalize_tags_cleaning(self):
        """Tags should be cleaned into a proper dict."""
        raw = [
            {
                "UsageDate": "2025-01-15",
                "PreTaxCost": 5.0,
                "SubscriptionId": "sub-001",
                "ResourceGroup": "rg",
                "ResourceId": "res",
                "ResourceName": "r",
                "ServiceName": "S",
                "ResourceType": "T",
                "ResourceLocation": "eastus",
                "Tags": {"env": "prod", "team": "platform", "empty": None},
            }
        ]
        records = self.normalizer.normalize_cost_rows(raw)
        assert records[0].tags == {"env": "prod", "team": "platform"}

    def test_build_aggregations(self):
        """Test aggregation row generation."""
        from tests.conftest import make_cost_record

        records = [
            make_cost_record(cost=10.0, service_name="Microsoft.Compute"),
            make_cost_record(cost=20.0, service_name="Microsoft.Compute"),
            make_cost_record(cost=5.0, service_name="Microsoft.Storage"),
        ]

        aggregations = self.normalizer.build_aggregations(records, "daily")
        assert len(aggregations) > 0
        # Should have aggregations for subscription, service, resource_group, resource_type
        dimensions = {a.dimension for a in aggregations}
        assert "subscription" in dimensions
        assert "service" in dimensions

    def test_region_normalization(self):
        """Test various region format normalisations."""
        assert self.normalizer._normalize_region("eastus") == "East US"
        assert self.normalizer._normalize_region("westeurope") == "West Europe"
        assert self.normalizer._normalize_region("centralindia") == "Central India"
        assert self.normalizer._normalize_region("some-unknown-region") == "some-unknown-region"
        assert self.normalizer._normalize_region("") == "Unknown"

    def test_date_parsing(self):
        """Test parsing various date formats."""
        dt = self.normalizer._parse_date("2025-01-15")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15

        dt2 = self.normalizer._parse_date("2025-01-15T10:30:00Z")
        assert dt2.hour == 10

        dt3 = self.normalizer._parse_date(datetime(2025, 3, 1))
        assert dt3 == datetime(2025, 3, 1)

    def test_reset_dedup_cache(self):
        """After reset, previously seen rows should be accepted again."""
        row = {
            "UsageDate": "2025-01-15", "PreTaxCost": 10.0,
            "SubscriptionId": "sub-001", "ResourceGroup": "rg",
            "ResourceId": "res", "ResourceName": "r",
            "ServiceName": "S", "ResourceType": "T", "ResourceLocation": "eastus",
        }
        self.normalizer.normalize_cost_rows([row])
        assert len(self.normalizer.normalize_cost_rows([row])) == 0

        self.normalizer.reset_dedup_cache()
        assert len(self.normalizer.normalize_cost_rows([row])) == 1
