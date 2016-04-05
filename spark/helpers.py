import os


def get_full_url(reversed_url):
    return '{0}{1}'.format(os.environ['DOMAIN_URL'], reversed_url)
