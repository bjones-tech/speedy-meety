#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spark.settings")

    os.environ.setdefault("REDISCLOUD_URL", "")
    os.environ.setdefault("SPARK_TOKEN", "")
    os.environ.setdefault("TROPO_PHONE_NUMBER", "")
    os.environ.setdefault("SIP_NUMBER", "")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
