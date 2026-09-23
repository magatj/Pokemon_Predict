# DNS module
#
# Route53 records and the ACM certificate for a custom domain. Optional: the
# CloudFront domain works on its own.
#
# Planned resources:
#   aws_acm_certificate.main            - must be in us-east-1 for CloudFront
#   aws_acm_certificate_validation.main
#   aws_route53_record.validation
#   aws_route53_record.apex

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
