from __future__ import absolute_import

import os
import re
import time
from datetime import datetime
from datetime import timedelta

from celery import shared_task
from django.core.urlresolvers import reverse

from spark.helpers import get_full_url
from .models import Meeting, Topic
from .calls import (
    get_message_details,
    send_message,
    get_rooms,
    get_room_details,
    get_room_memberships,
    delete_room,
    get_webhooks,
    create_webhook,
    send_signal,
    create_session
)


def send_welcome_message(room_id):
    welcome_message = []
    welcome_message.append('At your service to provide a more efficient meeting experience')
    welcome_message.append('')
    welcome_message.append('Initiating a meeting is as simple as typing:')
    welcome_message.append('/meet10 Topic 1, Topic 2, etc...')
    welcome_message.append('')
    welcome_message.append('For more information, please visit {0}'.format(os.environ['DOMAIN_URL']))

    send_message(text='\n'.join(welcome_message), room_id=room_id)


@shared_task()
def update_bot():
    for room in get_rooms():
        try:
            room_memberships = get_room_memberships(room['id'])

            if len(room_memberships) == 1:
                delete_room(room['id'])

            if len(room_memberships) > 2:
                filter = 'roomId={0}'.format(room['id'])
                filter_list = [webhook['filter'] for webhook in get_webhooks()]
                room = get_room_details(room['id'])

                if filter not in filter_list:
                    create_webhook(
                        name='{0} Webhook'.format(room['title']),
                        room_id=room['id']
                    )

                    send_welcome_message(room_id=room['id'])
        except KeyError:
            None


def route_request(resource, event, data):
    if resource == 'messages' and event == 'created':
        message = get_message_details(data['id'])

        help_match = re.match(pattern=r'(?i)^/+MEET\?$', string=message['text'])

        if help_match:
            send_welcome_message(room_id=message['roomId'])
            return None

        try:
            meeting = Meeting.objects.get(room_id=message['roomId'])

            start_match = re.match(pattern=r'(?i)^/+START$', string=message['text'])

            if start_match and meeting.state == Meeting.STAGED:
                start_meeting.delay(meeting)

            status_match = re.match(pattern=r'(?i)^/+STATUS$', string=message['text'])

            if status_match and meeting.state == Meeting.IN_PROGRESS:
                get_meeting_status(meeting)

            next_match = re.match(pattern=r'(?i)^/+NEXT$', string=message['text'])

            if next_match and meeting.state == Meeting.IN_PROGRESS:
                meeting.queue_next_topic = True
                meeting.save()

            cancel_match = re.match(pattern=r'(?i)^/+CANCEL$', string=message['text'])

            if cancel_match:
                cancel_meeting(meeting)


        except Meeting.DoesNotExist:
            meet_match = re.match(pattern=r'(?i)^/+MEET(?P<parameters>.*)', string=message['text'])

            if meet_match:
                try:
                    initiate_meeting(parameters=meet_match.group('parameters'), room_id=message['roomId'])
                except ValueError as error:
                    send_message(text=error.args[0], room_id=message['roomId'])


def initiate_meeting(parameters, room_id):
    parameters_match = re.match(pattern=r'(?i)^(?P<sip>|\$)(?P<time>|\!|[0-9]+)\s(?P<topics>.*)', string=parameters)

    if not parameters_match:
        raise ValueError('Invalid parameters')

    meeting_length = 10
    spark_audio = False

    dollar_sign_pattern = r'^\$$'

    if re.match(dollar_sign_pattern, parameters_match.group('sip')):
        spark_audio = True

    digit_pattern = r'^\d+$'
    exclamation_pattern = r'^\!$'

    if re.match(digit_pattern, parameters_match.group('time')):
        meeting_length = int(parameters_match.group('time'))

        if meeting_length < 1 or meeting_length > 30:
            raise ValueError('Meeting length is out of range')

    elif re.match(exclamation_pattern, parameters_match.group('time')):
        current_minute = datetime.now().minute

        if current_minute < 30:
            meeting_length = 30 - current_minute
        else:
            meeting_length = 60 - current_minute

    topics = []

    for topic in parameters_match.group('topics').strip().split(','):
        if topic.strip() and topic not in topics:
            topics.append(topic.strip())

        if meeting_length == 1 and len(topics) == 4 * meeting_length:
            break
        if meeting_length == 2 and len(topics) == 3 * meeting_length:
            break
        elif (meeting_length >= 3 and meeting_length <= 5) and len(topics) == 2 * meeting_length:
            break
        elif len(topics) == 10:
            break

    if len(topics) > 0:
        meeting = Meeting.create(
            room=get_room_details(room_id),
            meeting_length=meeting_length,
            topic_count=len(topics),
            spark_audio=spark_audio
        )

        meeting.save()

        for topic in topics:
            meeting.topic_set.create(name=topic)

        stage_meeting.delay(meeting)

        return None

    raise ValueError('Topics were not specified')


@shared_task()
def stage_meeting(meeting):
    initial_message = []
    initial_message.append('A meeting for the following topics has been initiated...')

    for topic in meeting.topic_set.all().order_by('pk'):
        initial_message.append('\t{0}'.format(topic))

    MINUTES = 1
    SECONDS = 2

    topic_time_span = str(timedelta(seconds=meeting.topic_time_limit)).split(':')

    initial_message.append('')
    initial_message.append('Meeting length: {0} minutes'.format(meeting.length))
    initial_message.append(
        'Time limit for each topic: {0} minutes {1} seconds'.format(
            topic_time_span[MINUTES],
            topic_time_span[SECONDS]
        ))

    initial_message.append('')

    if meeting.spark_audio == True:
        initial_message.append('Audio/Video: Call Spark Room')
    else:
        initial_message.append('Phone:\t{0}'.format(os.environ['TROPO_PHONE_NUMBER']))
        initial_message.append('SIP:\t\t{0}'.format(os.environ['SIP_NUMBER']))
        initial_message.append('ID:\t\t{0}'.format(meeting.voice_id))

    initial_message.append('')

    initial_message.append('Type "/START" to begin')
    initial_message.append('or meeting will automatically start in 1 minute')

    send_message(text='\n'.join(initial_message), room_id=meeting.room_id)

    if meeting.spark_audio == True:
        room = get_room_details(meeting.room_id)
        message = 'Meeting has been initiated'
        create_session(sip_address=room['sipAddress'], message=message)

    time.sleep(60)

    try:
        meeting.refresh_from_db()

        if meeting.state == Meeting.STAGED:
            start_meeting.delay(meeting)
    except Meeting.DoesNotExist:
        pass


@shared_task()
def start_meeting(meeting):
    try:
        meeting.state = Meeting.IN_PROGRESS
        meeting.save()

        for topic in meeting.topic_set.all().order_by('pk'):
            start_text = []
            start_text.append('########################')
            start_text.append('Topic: {0}'.format(topic.name))
            start_text.append('########################')

            start_message = send_message(text='\n'.join(start_text), room_id=meeting.room_id)

            topic.message_id = start_message['id']
            topic.time_left = meeting.topic_time_limit
            topic.save()

            meeting.current_topic = topic
            meeting.save()

            if meeting.spark_audio == True:
                room = get_room_details(meeting.room_id)
                message = 'Current topic: {0}'.format(topic.name)
                create_session(sip_address=room['sipAddress'], message=message)

            for caller in meeting.caller_set.all():
                send_signal(session_id=caller.session_id, signal='next')

            while topic.time_left != 0:
                if meeting.topic_time_limit >= 240 and topic.time_left == 120:
                    send_message(text='2 minute warning!', room_id=meeting.room_id)

                if meeting.topic_time_limit >= 120 and topic.time_left == 60:
                    send_message(text='1 minute warning!', room_id=meeting.room_id)

                if meeting.topic_time_limit >= 60 and topic.time_left == 15:
                    send_message(text='15 second warning!', room_id=meeting.room_id)

                time.sleep(1)

                meeting.refresh_from_db()

                if meeting.queue_next_topic:
                    topic.time_left = 0
                    meeting.queue_next_topic = False
                else:
                    topic.time_left -= 1

                topic.save()
                meeting.save()

        complete_text = []
        complete_text.append('########################')
        complete_text.append('Meeting complete')
        complete_text.append('########################')

        complete_message = send_message(text='\n'.join(complete_text), room_id=meeting.room_id)

        meeting.complete_id = complete_message['id']
        meeting.state = Meeting.COMPLETED
        meeting.save()

        if meeting.spark_audio == True:
            room = get_room_details(meeting.room_id)
            message = 'Meeting is complete'
            create_session(sip_address=room['sipAddress'], message=message)

        for caller in meeting.caller_set.all():
            send_signal(session_id=caller.session_id, signal='exit')

        if meeting.voice_used == True:
            count = 0
            topic = Topic.objects.get(pk=meeting.current_topic.pk)

            while count < 30 and not topic.transcription:
                topic.refresh_from_db()
                time.sleep(1)
                count += 1

            file_url = get_full_url(reverse('home:pdf', kwargs={'meeting_pk': meeting.pk}))
            send_message(text=None, room_id=meeting.room_id, file_url=file_url)

        meeting.delete()
    except Meeting.DoesNotExist:
        pass


def get_meeting_status(meeting):
    MINUTES = 1
    SECONDS = 2

    topic_time_span = str(timedelta(seconds=meeting.current_topic.time_left)).split(':')

    status = []
    status.append('Current topic: {0}'.format(meeting.current_topic.name))
    status.append('Time left for topic: {0} minutes {1} seconds'.format(
        topic_time_span[MINUTES],
        topic_time_span[SECONDS]
    ))

    send_message(text='\n'.join(status), room_id=meeting.room_id)


def cancel_meeting(meeting):
    meeting.state = Meeting.CANCELED
    meeting.save()

    message = 'Meeting has been canceled'

    if meeting.spark_audio == True:
        room = get_room_details(meeting.room_id)
        create_session(sip_address=room['sipAddress'], message=message)

    for caller in meeting.caller_set.all():
        send_signal(session_id=caller.session_id, signal='exit')

    send_message(text=message, room_id=meeting.room_id)
    meeting.delete()
