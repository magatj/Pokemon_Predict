terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region
}

# CloudFront requires its certificate in us-east-1 regardless of the main region.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
