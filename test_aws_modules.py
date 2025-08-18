#!/usr/bin/env python3
"""
Test script to verify AWS modules can be imported correctly
"""

def test_imports():
    try:
        print("Testing AWS EKS module import...")
        from aws.eks import info as eks_info
        print("✓ EKS module imported successfully")
        
        print("Testing AWS Fargate module import...")
        from aws.fargate import info as fargate_info
        print("✓ Fargate module imported successfully")
        
        print("Testing AWS CodePipeline build module import...")
        from aws.codepipeline import build as codepipeline_build
        print("✓ CodePipeline build module imported successfully")
        
        print("Testing AWS CodePipeline deploy module import...")
        from aws.codepipeline import deploy as codepipeline_deploy
        print("✓ CodePipeline deploy module imported successfully")
        
        print("\n✅ All AWS modules imported successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()