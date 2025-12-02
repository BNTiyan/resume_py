#!/bin/bash
# Example script to test quick_apply.py

echo "🧪 Quick Apply Tool - Test Script"
echo "=================================="
echo ""

# Test 1: Show help
echo "Test 1: Showing help menu..."
python3 quick_apply.py --help
echo ""

# Test 2: Example with job description text (simulated)
echo "Test 2: Testing with inline job description..."
echo ""

JOB_DESC="Senior Machine Learning Engineer

We are seeking an experienced ML Engineer to join our team.

Requirements:
- 5+ years of experience in Python, TensorFlow, PyTorch
- Experience with AWS/GCP cloud platforms
- Strong understanding of ML algorithms and deep learning
- Experience with MLOps tools and practices

Responsibilities:
- Design and deploy ML models at scale
- Build ML pipelines and infrastructure
- Collaborate with cross-functional teams
- Optimize model performance and monitoring"

# Uncomment to run actual test (requires API keys)
# python3 quick_apply.py \
#   --job-description "$JOB_DESC" \
#   --company "Google" \
#   --title "Senior ML Engineer" \
#   --output "output/test_apply"

echo "✅ To run a real test, uncomment the command above and add your API keys"
echo ""
echo "Quick examples:"
echo ""
echo "1. From job link:"
echo "   python3 quick_apply.py --job-link \"https://boards.greenhouse.io/stripe/jobs/123\""
echo ""
echo "2. From text file:"
echo "   python3 quick_apply.py --jd-file \"job_description.txt\" --company \"Stripe\" --title \"Backend Engineer\""
echo ""
echo "3. With custom output:"
echo "   python3 quick_apply.py --job-link \"...\" --output \"my_applications/stripe\""
echo ""

