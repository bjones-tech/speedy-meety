import json
import os

import requests
from django.core.urlresolvers import reverse

from spark.helpers import get_full_url

SPARK_HEADERS = {
    'Authorization': 'Bearer {0}'.format(os.environ['SPARK_TOKEN'])
}

TROPO_HEADERS = {
    'accept': 'application/json',
    'content-type': 'application/json'
}


# Spark Message calls

def get_message_details(message_id):
    url = 'https://api.ciscospark.com/v1/messages/{0}'.format(message_id)
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()


def send_message(text, room_id, file_url=None):
    url = 'https://api.ciscospark.com/v1/messages'

    files = None

    if file_url:
        files = [file_url]

    data = {
        'roomId': room_id,
        'text': text,
        'files': files
    }

    headers = SPARK_HEADERS.copy()
    headers['content-type'] = 'application/json'

    r = requests.post(url, data=json.dumps(data), headers=headers)
    return r.json()


# Spark Room calls

def get_rooms():
    url = 'https://api.ciscospark.com/v1/rooms'
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()['items']


def get_room_details(room_id):
    url = 'https://api.ciscospark.com/v1/rooms/{0}?showSipAddress=true'.format(room_id)
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()


def get_room_messages(room_id):
    url = 'https://api.ciscospark.com/v1/messages?roomId={0}'.format(room_id)
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()['items']


def get_room_memberships(room_id):
    url = 'https://api.ciscospark.com/v1/memberships?roomId={0}'.format(room_id)
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()['items']


def delete_room(room_id):
    url = 'https://api.ciscospark.com/v1/rooms/{0}'.format(room_id)
    requests.delete(url, headers=SPARK_HEADERS)


# Spark Webhook calls

def get_webhooks():
    url = 'https://api.ciscospark.com/v1/webhooks'
    r = requests.get(url, headers=SPARK_HEADERS)
    return r.json()['items']


def create_webhook(name, room_id):
    url = 'https://api.ciscospark.com/v1/webhooks'

    data = {
        'name': name,
        'targetUrl': get_full_url(reverse('home:webhook')),
        'resource': 'messages',
        'event': 'created',
        'filter': 'roomId={0}'.format(room_id)
    }

    requests.post(url, data=data, headers=SPARK_HEADERS)


# Tropo calls

def send_signal(session_id, signal):
    url = 'https://api.tropo.com/1.0/sessions/{0}/signals?action=signal&value={1}'.format(session_id, signal)
    requests.post(url, headers=TROPO_HEADERS)


def create_session(sip_address, message):
    url = 'https://api.tropo.com/1.0/sessions'

    data = {
        'token': os.environ['TROPO_TOKEN'],
        'sipAddress': 'sip:{0};transport=tcp'.format(sip_address),
        'msg': message
    }

    return requests.post(url, data=json.dumps(data), headers=TROPO_HEADERS).content
