import json

from datetime import datetime
from io import BytesIO

from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from spark.helpers import get_full_url
from .models import Meeting, MeetingTranscription, Caller, Topic
from .serializers import WebhookSerializer
from .tasks import route_request
from .tropo import Tropo, Result


# Spark Webhook

class Webhook(APIView):
    def post(self, request, format=None):
        serializer = WebhookSerializer(data=request.data)
        if serializer.is_valid():
            route_request(
                resource=serializer.data['resource'],
                event=serializer.data['event'],
                data=serializer.data['data']
            )
            return Response(None, status=status.HTTP_202_ACCEPTED)
        return Response(None, status=status.HTTP_400_BAD_REQUEST)


# Spark PDF Request

def meeting_pdf(request, meeting_pk):
    try:
        meeting = Meeting.objects.get(id=meeting_pk)

        filename = 'Meeting Transcription-{0}.pdf'.format(datetime.now())
        buffer = BytesIO()
        meeting_transcription = MeetingTranscription(meeting=meeting, buffer=buffer)
        pdf = meeting_transcription.create_pdf()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
        response.write(pdf)
    except Meeting.DoesNotExist:
        response = Http404

    return response


# Tropo Hooks

@csrf_exempt
def voice_initiate(request):
    tropo = Tropo()

    if request.method == 'POST':
        tropo.ask(
            attempts=3,
            say='Please enter meeting ID',
            choices='[4 DIGITS]',
            timeout=10
        )

        tropo.on(
            event='continue',
            next=get_full_url(reverse('home:voice_validate'))
        )

    json = tropo.RenderJson()
    return HttpResponse(json)


@csrf_exempt
def voice_validate(request):
    tropo = Tropo()

    if request.method == 'POST':
        meetings = Meeting.objects.all()

        if len(meetings) > 0:
            body = request.body.decode('utf-8')
            result = Result(body)
            session_id = result.getSessionID()
            entered_id = result.getValue()
            voice_ids = [meeting.voice_id for meeting in meetings]

            if entered_id in voice_ids:
                try:
                    meeting = Meeting.objects.get(voice_id=entered_id)
                    meeting.caller_set.create(session_id=session_id)

                    if meeting.voice_used == False:
                        meeting.voice_used = True
                        meeting.save()

                    tropo.on(
                        event='continue',
                        next=get_full_url(reverse('home:voice_next', kwargs={'meeting_pk': meeting.pk}))
                    )

                    tropo.on(
                        event='hangup',
                        next=get_full_url(reverse('home:voice_hangup', kwargs={'meeting_pk': meeting.pk}))
                    )

                except Meeting.DoesNotExist:
                    tropo.say('Invalid entry')
            else:
                tropo.say('Invalid entry')
        else:
            tropo.say('Invalid entry')

    json = tropo.RenderJson()
    return HttpResponse(json)


@csrf_exempt
def voice_next(request, meeting_pk):
    tropo = Tropo()

    if request.method == 'POST':
        try:
            meeting = Meeting.objects.get(pk=meeting_pk)

            if meeting.state == Meeting.STAGED:
                tropo.say('Meeting has not started')
            elif meeting.state == Meeting.IN_PROGRESS:
                topic = Topic.objects.get(pk=meeting.current_topic.pk)

                if topic.recording == False:
                    tropo.stopRecording()

                    uri = get_full_url(reverse('home:voice_transcribe', kwargs={'topic_pk': topic.pk}))

                    tropo.startRecording(
                        url='http://hosting.tropo.com/5050915/www',
                        transcriptionOutURI=uri
                    )

                    topic.recording = True
                    topic.save()

                tropo.say('Current topic: {0}'.format(topic.name))

            tropo.conference(
                id=meeting.voice_id,
                terminator='*',
                allowSignals=['next', 'exit']
            )

            tropo.on(
                event='continue',
                next=get_full_url(reverse('home:voice_next', kwargs={'meeting_pk': meeting.pk}))
            )

            tropo.on(
                event='next',
                next=get_full_url(reverse('home:voice_next', kwargs={'meeting_pk': meeting.pk}))
            )

            tropo.on(
                event='hangup',
                next=get_full_url(reverse('home:voice_hangup', kwargs={'meeting_pk': meeting.pk}))
            )

            tropo.on(
                event='exit',
                next=get_full_url(reverse('home:voice_hangup', kwargs={'meeting_pk': meeting.pk}))
            )
        except Meeting.DoesNotExist:
            pass

    json = tropo.RenderJson()
    return HttpResponse(json)


@csrf_exempt
def voice_hangup(request, meeting_pk):
    tropo = Tropo()

    if request.method == 'POST':
        try:
            body = request.body.decode('utf-8')
            result = Result(body)
            session_id = result.getSessionID()
            meeting = Meeting.objects.get(pk=meeting_pk)

            if meeting.state == Meeting.COMPLETED:
                tropo.say('Meeting is complete')
            elif meeting.state == Meeting.CANCELED:
                tropo.say('Meeting has been cancelled')

            caller = meeting.caller_set.get(session_id=session_id)
            caller.delete()
        except (Meeting.DoesNotExist, Caller.DoesNotExist):
            pass

    json = tropo.RenderJson()
    return HttpResponse(json)


@csrf_exempt
def voice_transcribe(request, topic_pk):
    if request.method == 'POST':
        try:
            body = request.body.decode('utf-8')
            topic = Topic.objects.get(pk=topic_pk)
            topic.transcription = json.loads(body)['result']['transcription']
            topic.save()
        except Topic.DoesNotExist:
            pass

    return HttpResponse()
