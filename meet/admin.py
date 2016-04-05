from django.contrib import admin

from .models import Meeting, Topic, Caller


class TopicInline(admin.StackedInline):
    model = Topic
    extra = 0


class CallerInline(admin.StackedInline):
    model = Caller
    extra = 0


class MeetingAdmin(admin.ModelAdmin):
    list_display = ('room_name', 'voice_id', 'voice_used', 'state', 'current_topic', 'length', 'topic_time_limit')
    fields = ['room_name', 'room_id', 'complete_id']
    inlines = [TopicInline, CallerInline]


admin.site.register(Meeting, MeetingAdmin)
