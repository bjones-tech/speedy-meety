from datetime import timedelta
from random import randint
from django.db import models
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def get_voice_id():
    return str(randint(1000, 9999))


class Meeting(models.Model):
    STAGED = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    CANCELED = 3

    MEETING_STATES = (
        (STAGED, 'Staged'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (CANCELED, 'Canceled')
    )

    room_name = models.CharField(max_length=200, default='none')
    room_id = models.CharField(max_length=200, default='none')
    voice_id = models.CharField(max_length=200, default=get_voice_id)
    voice_used = models.BooleanField(default=False)
    spark_audio = models.BooleanField(default=False)
    state = models.IntegerField(choices=MEETING_STATES, default=STAGED)
    length = models.IntegerField(default=0)
    topic_time_limit = models.IntegerField(default=0)
    current_topic = models.OneToOneField('Topic', on_delete=models.SET_NULL, related_name='+', null=True)
    queue_next_topic = models.BooleanField(default=False)
    complete_id = models.CharField(max_length=200, default='none')

    @classmethod
    def create(cls, room, meeting_length, topic_count, spark_audio):
        topic_time_limit = int(timedelta(minutes=meeting_length).seconds / topic_count)

        meeting = cls(
            room_name=room['title'],
            room_id=room['id'],
            length=meeting_length,
            topic_time_limit=topic_time_limit,
            spark_audio=spark_audio
        )

        return meeting

    def __str__(self):
        return self.room_name


class Topic(models.Model):
    name = models.CharField(max_length=200, default='none')
    message_id = models.CharField(max_length=200, default='none')
    time_left = models.IntegerField(default=0)
    recording = models.BooleanField(default=False)
    transcription = models.TextField(blank=True, null=True)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Caller(models.Model):
    name = models.CharField(max_length=200, default='none')
    session_id = models.CharField(max_length=200, default='none')
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


# PDF Transcription

class MeetingTranscription(object):
    def __init__(self, meeting, buffer):
        self.meeting = meeting
        self.buffer = buffer
        self.pagesize = letter
        self.width, self.height = self.pagesize

    def create_pdf(self):
        buffer = self.buffer

        doc = SimpleDocTemplate(
            buffer,
            rightMargin=48,
            leftMargin=48,
            topMargin=48,
            bottomMargin=48,
            pagesize=self.pagesize
        )

        elements = []

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='centered', alignment=TA_CENTER))

        for topic in self.meeting.topic_set.all().order_by('pk'):
            elements.append(Paragraph(topic.name, styles['Heading1']))

            if topic.transcription:
                elements.append(Paragraph(topic.transcription, styles['Normal']))
            else:
                elements.append(Paragraph('Unable to collect transcription', styles['Normal']))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
