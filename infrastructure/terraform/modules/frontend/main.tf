# Frontend module
#
# S3 origin plus CloudFront for the built React bundle and the generated JSON.
# Replaces GitLab Pages; the bundle itself is byte-identical.
#
# Planned resources:
#   aws_s3_bucket.site                     - private origin bucket
#   aws_s3_bucket_public_access_block.site - block all public access
#   aws_cloudfront_origin_access_control   - OAC so only CloudFront can read
#   aws_cloudfront_distribution.site       - SPA distribution, 404 -> index.html
#   aws_s3_bucket_policy.site              - grant the distribution read access

# Resources are intentionally not declared: the GitLab Pages MVP
# provisions nothing. See infrastructure/terraform/README.md.
