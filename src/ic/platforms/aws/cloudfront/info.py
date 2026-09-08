"""
AWS CloudFront distribution information collector and renderer.

This module provides classes to collect CloudFront distribution details
and render them in a user-friendly table format.
"""

import boto3
from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from botocore.exceptions import ClientError, NoCredentialsError

from common.progress_decorator import ManualProgress
import boto3


class CloudFrontCollector:
    """Collects CloudFront distribution information from AWS."""
    
    def __init__(self):
        self.console = Console()
    
    def collect_distributions(self, account_profiles: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Collect CloudFront distribution information from multiple accounts.
        
        Args:
            account_profiles: Dictionary mapping account names to AWS profile names
            
        Returns:
            List of distribution information dictionaries
        """
        import time
        
        distributions = []
        total_accounts = len(account_profiles)
        
        with ManualProgress(f"Collecting CloudFront distributions from {total_accounts} account(s)", total=total_accounts) as progress:
            completed = 0
            for account_name, profile_name in account_profiles.items():
                start_time = time.time()
                try:
                    session = boto3.Session(profile_name=profile_name)
                    account_distributions = self._get_account_distributions(session, account_name)
                    distributions.extend(account_distributions)
                    
                    # Calculate processing time
                    processing_time = time.time() - start_time
                    completed += 1
                    progress.update(
                        f"Processed {account_name} - Found {len(account_distributions)} distributions ({processing_time:.2f}s)",
                        advance=1
                    )
                    
                except Exception as e:
                    completed += 1
                    self.console.print(f"Failed to collect CloudFront data for {account_name}: {e}")
                    progress.update(f"Failed {account_name} - {str(e)[:50]}...", advance=1)
        
        return distributions
    
    def _get_account_distributions(self, session: boto3.Session, account_name: str) -> List[Dict[str, str]]:
        """
        Get CloudFront distributions for a specific account.
        
        Args:
            session: AWS session for the account
            account_name: Name of the AWS account
            
        Returns:
            List of distribution information dictionaries
        """
        try:
            cloudfront_client = session.client('cloudfront')
            
            # List all distributions
            response = cloudfront_client.list_distributions()
            distributions = []
            
            if 'DistributionList' in response and 'Items' in response['DistributionList']:
                for distribution in response['DistributionList']['Items']:
                    dist_info = self.get_distribution_details(distribution, account_name)
                    distributions.append(dist_info)
            
            return distributions
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.console.print(f"⚠️  Access denied for CloudFront in {account_name}")
            else:
                self.console.print(f"❌ CloudFront API error in {account_name}: {e}")
            return []
        except NoCredentialsError:
            self.console.print(f"❌ No credentials available for {account_name}")
            return []
    
    def get_distribution_details(self, distribution: Dict[str, Any], account_name: str) -> Dict[str, str]:
        """
        Extract and format distribution details.
        
        Args:
            distribution: CloudFront distribution data from AWS API
            account_name: Name of the AWS account
            
        Returns:
            Dictionary with formatted distribution information
        """
        return {
            'account': account_name,
            'ID': distribution.get('Id', 'N/A'),
            'Name': distribution.get('Comment', 'N/A') or 'N/A',
            '원본(Origin)': self.get_primary_origin(distribution.get('Origins', {}).get('Items', [])),
            '도메인(Domain)': distribution.get('DomainName', 'N/A'),
            'Class': self.format_price_class(distribution.get('PriceClass', 'PriceClass_All'))
        }
    
    def get_primary_origin(self, origins: List[Dict[str, Any]]) -> str:
        """
        Get the primary origin or indicate multiple origins.
        
        Args:
            origins: List of origin configurations
            
        Returns:
            Primary origin domain or "Multiple" indicator
        """
        if not origins:
            return 'N/A'
        elif len(origins) == 1:
            return origins[0].get('DomainName', 'N/A')
        else:
            return f'Multiple ({len(origins)})'
    
    def format_price_class(self, price_class: str) -> str:
        """
        Convert technical price class names to human-readable format.
        
        Args:
            price_class: Technical price class name from AWS
            
        Returns:
            Human-readable price class description
        """
        price_class_mapping = {
            'PriceClass_All': 'All Edge Locations',
            'PriceClass_200': 'North America and Europe Only',
            'PriceClass_100': 'North America Only'
        }
        
        return price_class_mapping.get(price_class, price_class)


class CloudFrontRenderer:
    """Renders CloudFront distribution information in table format."""
    
    def __init__(self):
        self.console = Console()
    
    def render_distributions(self, distributions: List[Dict[str, str]]) -> None:
        """
        Render CloudFront distributions in a Rich table.
        
        Args:
            distributions: List of distribution information dictionaries
        """
        if not distributions:
            self.console.print("📋 No CloudFront distributions found.")
            return
        
        table = Table(title="CloudFront Distributions")
        table.add_column("Account", style="cyan", no_wrap=True)
        table.add_column("ID", style="green", no_wrap=True)
        table.add_column("Name", style="yellow")
        table.add_column("원본(Origin)", style="blue")
        table.add_column("도메인(Domain)", style="magenta")
        table.add_column("Class", style="red")
        
        for dist in distributions:
            table.add_row(
                dist['account'],
                dist['ID'],
                dist['Name'],
                dist['원본(Origin)'],
                dist['도메인(Domain)'],
                dist['Class']
            )
        
        self.console.print(table)
        self.console.print(f"\n📊 Total distributions: {len(distributions)}")


import argparse
from ic.core.interfaces import BaseCommand, CommandResult
from common.utils import get_env_accounts, get_profiles


class AwsCloudfrontInfoCommand(BaseCommand):
    """AWS CloudFront distributions information command."""

    @classmethod
    def add_arguments(cls, parser):
        cls.add_common_arguments(parser)
        parser.add_argument('-a', '--account', help='특정 AWS 계정 ID 목록(,) (없으면 .env 사용)')
        parser.add_argument('-n', '--name', help='CloudFront 배포 이름/도메인 필터 (부분 일치)')

    def execute(self, args, config=None) -> CommandResult:
        accounts = get_env_accounts(getattr(args, 'account', None))
        profiles_map = get_profiles()
        
        target_profiles = {}
        for acct in accounts:
            prof = profiles_map.get(acct)
            if prof:
                target_profiles[acct] = prof
                
        collector = CloudFrontCollector()
        distributions = collector.collect_distributions(target_profiles)
        
        # Apply name filter if requested
        name_filter = getattr(args, 'name', None)
        if name_filter:
            name_lower = name_filter.lower()
            distributions = [
                d for d in distributions
                if name_lower in d.get('Name', '').lower()
                or name_lower in d.get('도메인(Domain)', '').lower()
                or name_lower in d.get('ID', '').lower()
            ]
            
        renderer = CloudFrontRenderer()
        return CommandResult(
            data=distributions,
            table_renderer=lambda data, verbose=False: renderer.render_distributions(data),
        )


def main(args, config=None):
    AwsCloudfrontInfoCommand().run(args, config)


def add_arguments(parser):
    AwsCloudfrontInfoCommand.add_arguments(parser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS CloudFront 정보 조회")
    add_arguments(parser)
    args = parser.parse_args()
    main(args)