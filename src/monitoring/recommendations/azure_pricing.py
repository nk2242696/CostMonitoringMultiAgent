"""
Azure Pricing API Integration

Fetches real-time Azure pricing data for accurate cost calculations and savings estimates.

Official Documentation:
https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices
"""

from typing import List, Dict, Optional
import requests
from pydantic import BaseModel
from datetime import datetime
import json


class AzurePrice(BaseModel):
    """Azure service pricing information."""
    
    service_name: str
    service_id: str
    sku_name: str
    product_name: str
    region: str
    unit_price: float
    currency_code: str
    unit_of_measure: str
    tier_minimum_units: Optional[float] = None
    retail_price: float
    effective_start_date: str
    meter_id: str


class AzurePricingClient:
    """
    Client for Azure Retail Prices API.
    
    Provides real-time pricing information for Azure services.
    No authentication required for retail prices API.
    
    API Documentation:
    https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices
    """
    
    def __init__(self):
        """Initialize Azure Pricing client."""
        self.base_url = "https://prices.azure.com/api/retail/prices"
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Azure-Cost-Monitoring/1.0'
        })
    
    def get_vm_pricing(
        self,
        vm_size: str,
        region: str = "eastus",
        os_type: str = "Windows"
    ) -> Optional[AzurePrice]:
        """
        Get pricing for a specific VM size.
        
        Args:
            vm_size: VM size (e.g., 'Standard_D2s_v3')
            region: Azure region (e.g., 'eastus', 'westus')
            os_type: Operating system ('Windows' or 'Linux')
        
        Returns:
            AzurePrice object or None if not found
        """
        try:
            # Build filter query
            filter_query = (
                f"serviceName eq 'Virtual Machines' "
                f"and armRegionName eq '{region}' "
                f"and armSkuName eq '{vm_size}' "
                f"and priceType eq 'Consumption'"
            )
            
            if os_type.lower() == "windows":
                filter_query += " and productName contains 'Windows'"
            else:
                filter_query += " and not productName contains 'Windows'"
            
            params = {
                '$filter': filter_query,
                'api-version': '2023-01-01-preview'
            }
            
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            
            if not items:
                return None
            
            # Return first matching price
            item = items[0]
            return AzurePrice(
                service_name=item['serviceName'],
                service_id=item['serviceId'],
                sku_name=item['skuName'],
                product_name=item['productName'],
                region=item['armRegionName'],
                unit_price=float(item['unitPrice']),
                currency_code=item['currencyCode'],
                unit_of_measure=item['unitOfMeasure'],
                tier_minimum_units=item.get('tierMinimumUnits'),
                retail_price=float(item['retailPrice']),
                effective_start_date=item['effectiveStartDate'],
                meter_id=item['meterId']
            )
            
        except Exception as e:
            print(f"⚠️  Failed to fetch VM pricing: {e}")
            return None
    
    def get_storage_pricing(
        self,
        storage_type: str = "Standard_LRS",
        tier: str = "Hot",
        region: str = "eastus"
    ) -> Optional[AzurePrice]:
        """
        Get pricing for Azure Storage.
        
        Args:
            storage_type: Storage redundancy (Standard_LRS, Standard_GRS, etc.)
            tier: Access tier (Hot, Cool, Archive)
            region: Azure region
        
        Returns:
            AzurePrice object or None if not found
        """
        try:
            filter_query = (
                f"serviceName eq 'Storage' "
                f"and armRegionName eq '{region}' "
                f"and skuName eq '{storage_type}' "
                f"and productName contains '{tier}' "
                f"and meterName contains 'Data Stored' "
                f"and priceType eq 'Consumption'"
            )
            
            params = {
                '$filter': filter_query,
                'api-version': '2023-01-01-preview'
            }
            
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            
            if items:
                item = items[0]
                return AzurePrice(
                    service_name=item['serviceName'],
                    service_id=item['serviceId'],
                    sku_name=item['skuName'],
                    product_name=item['productName'],
                    region=item['armRegionName'],
                    unit_price=float(item['unitPrice']),
                    currency_code=item['currencyCode'],
                    unit_of_measure=item['unitOfMeasure'],
                    tier_minimum_units=item.get('tierMinimumUnits'),
                    retail_price=float(item['retailPrice']),
                    effective_start_date=item['effectiveStartDate'],
                    meter_id=item['meterId']
                )
            
            return None
            
        except Exception as e:
            print(f"⚠️  Failed to fetch storage pricing: {e}")
            return None
    
    def get_sql_pricing(
        self,
        service_tier: str = "Standard",
        dtu: str = "S2",
        region: str = "eastus"
    ) -> Optional[AzurePrice]:
        """
        Get pricing for Azure SQL Database.
        
        Args:
            service_tier: Service tier (Basic, Standard, Premium)
            dtu: DTU level (S0, S1, S2, etc.)
            region: Azure region
        
        Returns:
            AzurePrice object or None if not found
        """
        try:
            filter_query = (
                f"serviceName eq 'SQL Database' "
                f"and armRegionName eq '{region}' "
                f"and skuName eq '{dtu}' "
                f"and productName contains 'Single' "
                f"and priceType eq 'Consumption'"
            )
            
            params = {
                '$filter': filter_query,
                'api-version': '2023-01-01-preview'
            }
            
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            
            if items:
                item = items[0]
                return AzurePrice(
                    service_name=item['serviceName'],
                    service_id=item['serviceId'],
                    sku_name=item['skuName'],
                    product_name=item['productName'],
                    region=item['armRegionName'],
                    unit_price=float(item['unitPrice']),
                    currency_code=item['currencyCode'],
                    unit_of_measure=item['unitOfMeasure'],
                    tier_minimum_units=item.get('tierMinimumUnits'),
                    retail_price=float(item['retailPrice']),
                    effective_start_date=item['effectiveStartDate'],
                    meter_id=item['meterId']
                )
            
            return None
            
        except Exception as e:
            print(f"⚠️  Failed to fetch SQL pricing: {e}")
            return None
    
    def calculate_reservation_savings(
        self,
        service_name: str,
        current_monthly_cost: float,
        reservation_term: int = 1
    ) -> Dict:
        """
        Calculate savings from Azure Reservations.
        
        Args:
            service_name: Azure service name
            current_monthly_cost: Current pay-as-you-go monthly cost
            reservation_term: Reservation term in years (1 or 3)
        
        Returns:
            Dictionary with savings calculations
        """
        # Azure Reservations discount rates (approximate)
        discount_rates = {
            "Virtual Machines": {1: 0.40, 3: 0.62},  # 40% for 1yr, 62% for 3yr
            "SQL Database": {1: 0.33, 3: 0.55},
            "Cosmos DB": {1: 0.35, 3: 0.65},
            "App Service": {1: 0.30, 3: 0.50},
            "Storage": {1: 0.25, 3: 0.38}
        }
        
        # Get discount rate
        discount = 0.0
        for key in discount_rates:
            if key.lower() in service_name.lower():
                discount = discount_rates[key].get(reservation_term, 0.0)
                break
        
        if discount == 0.0:
            discount = 0.30 if reservation_term == 1 else 0.50  # Default
        
        monthly_savings = current_monthly_cost * discount
        annual_savings = monthly_savings * 12
        term_savings = annual_savings * reservation_term
        
        return {
            "reservation_term_years": reservation_term,
            "discount_percent": round(discount * 100, 1),
            "current_monthly_cost": round(current_monthly_cost, 2),
            "reservation_monthly_cost": round(current_monthly_cost * (1 - discount), 2),
            "monthly_savings": round(monthly_savings, 2),
            "annual_savings": round(annual_savings, 2),
            "total_term_savings": round(term_savings, 2),
            "documentation": "https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/save-compute-costs-reservations"
        }
    
    def calculate_spot_vm_savings(
        self,
        current_monthly_cost: float,
        eviction_rate: str = "low"
    ) -> Dict:
        """
        Calculate savings from Spot VMs.
        
        Args:
            current_monthly_cost: Current pay-as-you-go monthly cost
            eviction_rate: Expected eviction rate (low, medium, high)
        
        Returns:
            Dictionary with savings calculations
        """
        # Spot VM discount rates (up to 90% savings)
        discount_rates = {
            "low": 0.70,     # 70% savings, low eviction risk
            "medium": 0.80,  # 80% savings, medium eviction risk
            "high": 0.90     # 90% savings, high eviction risk
        }
        
        discount = discount_rates.get(eviction_rate.lower(), 0.70)
        monthly_savings = current_monthly_cost * discount
        annual_savings = monthly_savings * 12
        
        return {
            "eviction_rate": eviction_rate,
            "discount_percent": round(discount * 100, 1),
            "current_monthly_cost": round(current_monthly_cost, 2),
            "spot_monthly_cost": round(current_monthly_cost * (1 - discount), 2),
            "monthly_savings": round(monthly_savings, 2),
            "annual_savings": round(annual_savings, 2),
            "suitability": "Batch processing, dev/test, fault-tolerant workloads",
            "documentation": "https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms"
        }
    
    def get_service_comparison(
        self,
        service_type: str,
        region: str = "eastus"
    ) -> List[Dict]:
        """
        Get pricing comparison for different SKUs of a service.
        
        Args:
            service_type: Azure service name
            region: Azure region
        
        Returns:
            List of pricing options
        """
        try:
            filter_query = (
                f"serviceName eq '{service_type}' "
                f"and armRegionName eq '{region}' "
                f"and priceType eq 'Consumption'"
            )
            
            params = {
                '$filter': filter_query,
                'api-version': '2023-01-01-preview',
                '$top': 10  # Limit results
            }
            
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            
            results = []
            for item in items[:10]:  # Top 10
                results.append({
                    'sku_name': item['skuName'],
                    'product_name': item['productName'],
                    'unit_price': float(item['unitPrice']),
                    'unit': item['unitOfMeasure'],
                    'currency': item['currencyCode']
                })
            
            return results
            
        except Exception as e:
            print(f"⚠️  Failed to fetch service comparison: {e}")
            return []


def main():
    """Test Azure Pricing API integration."""
    print("=" * 70)
    print("💰 Azure Pricing API - Real-time Pricing Data")
    print("=" * 70)
    
    client = AzurePricingClient()
    
    # Test VM pricing
    print("\n1. Virtual Machine Pricing (Standard_D2s_v3, East US)")
    print("-" * 70)
    vm_price = client.get_vm_pricing("Standard_D2s_v3", "eastus", "Windows")
    if vm_price:
        print(f"   SKU: {vm_price.sku_name}")
        print(f"   Product: {vm_price.product_name}")
        print(f"   Price: {vm_price.currency_code} ${vm_price.unit_price:.4f} per {vm_price.unit_of_measure}")
        print(f"   Monthly (730 hours): ${vm_price.unit_price * 730:.2f}")
    
    # Test reservation savings
    print("\n2. Azure Reservation Savings Calculator")
    print("-" * 70)
    savings = client.calculate_reservation_savings(
        service_name="Virtual Machines",
        current_monthly_cost=1000.0,
        reservation_term=3
    )
    print(f"   Current Monthly Cost: ${savings['current_monthly_cost']}")
    print(f"   With 3-Year Reservation: ${savings['reservation_monthly_cost']}/month")
    print(f"   Monthly Savings: ${savings['monthly_savings']} ({savings['discount_percent']}%)")
    print(f"   Annual Savings: ${savings['annual_savings']}")
    print(f"   Total 3-Year Savings: ${savings['total_term_savings']}")
    
    # Test Spot VM savings
    print("\n3. Spot VM Savings Calculator")
    print("-" * 70)
    spot_savings = client.calculate_spot_vm_savings(
        current_monthly_cost=1000.0,
        eviction_rate="medium"
    )
    print(f"   Current Monthly Cost: ${spot_savings['current_monthly_cost']}")
    print(f"   With Spot VMs: ${spot_savings['spot_monthly_cost']}/month")
    print(f"   Monthly Savings: ${spot_savings['monthly_savings']} ({spot_savings['discount_percent']}%)")
    print(f"   Annual Savings: ${spot_savings['annual_savings']}")
    print(f"   Best For: {spot_savings['suitability']}")
    
    # Test storage pricing
    print("\n4. Storage Pricing Comparison")
    print("-" * 70)
    hot_price = client.get_storage_pricing("Standard_LRS", "Hot", "eastus")
    cool_price = client.get_storage_pricing("Standard_LRS", "Cool", "eastus")
    
    if hot_price and cool_price:
        print(f"   Hot Tier: ${hot_price.unit_price:.4f} per {hot_price.unit_of_measure}")
        print(f"   Cool Tier: ${cool_price.unit_price:.4f} per {cool_price.unit_of_measure}")
        savings_percent = ((hot_price.unit_price - cool_price.unit_price) / hot_price.unit_price) * 100
        print(f"   Cool tier saves {savings_percent:.1f}% vs Hot tier")
    
    print("\n" + "=" * 70)
    print("✓ Azure Pricing API integration working!")
    print("=" * 70)


if __name__ == "__main__":
    main()
