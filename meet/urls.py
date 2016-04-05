import os

from django.conf.urls import url

from . import hooks

app_name = 'home'

urlpatterns = [
    # /home/webhook
    url(r'^webhook$', hooks.Webhook.as_view(), name='webhook'),

    # /home/1.pdf
    url(r'^(?P<meeting_pk>[0-9]+)\.pdf$', hooks.meeting_pdf, name='pdf'),

    # /home/voice/initiate
    url(r'^voice/initiate$', hooks.voice_initiate, name='voice_initiate'),

    # /home/voice/validate
    url(r'^voice/validate$', hooks.voice_validate, name='voice_validate'),

    # /home/voice/next/1
    url(r'^voice/next/(?P<meeting_pk>[0-9]+)$', hooks.voice_next, name='voice_next'),

    # /home/voice/hangup/1
    url(r'^voice/hangup/(?P<meeting_pk>[0-9]+)$', hooks.voice_hangup, name='voice_hangup'),

    # /home/voice/transcribe/1
    url(r'^voice/transcribe/(?P<topic_pk>[0-9]+)$', hooks.voice_transcribe, name='voice_transcribe'),
]
