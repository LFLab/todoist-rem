from functools import wraps
from collections import OrderedDict

from todoist import models

DEFAULT_MODELS = {
    "collaborators": models.Collaborator,
    "collaborator_states": models.CollaboratorState,
    "filters": models.Filter,
    "items": models.Item,
    "labels": models.Label,
    "live_notifications": models.LiveNotification,
    "notes": models.Note,
    "project_notes": models.ProjectNote,
    "projects": models.Project,
    "reminders": models.Reminder,
    "sections": models.Section,
}

BEFORE_CALL = "::before"
AFTER_CALL = "::after"


def register_emit_event(
    func,
    emitter,
    evt_fmt="{fname}{when}",
    when=(BEFORE_CALL, AFTER_CALL)
):
    @wraps(func)
    def _inner(*args, **kws):
        fname = func.__name__
        if BEFORE_CALL in when:
            emitter(evt_fmt.format(fname=fname, when=BEFORE_CALL),
                    *args, **kws)
        rv = func(*args, **kws)
        if AFTER_CALL in when:
            emitter(evt_fmt.format(fname=fname, when=AFTER_CALL),
                    *args, __return=rv, **kws)
        return rv

    return _inner


class ObservableDict(OrderedDict):
    def __init__(self, other, __evt, **kws):
        super().__init__(other, **kws)
        self.emitter = __evt

        evt_fmt = "{fname}{when}"
        pairs = [
            ("update", evt_fmt),
            ("pop", evt_fmt),
            ("clear", evt_fmt),
            ("__setitem__", "setitem{when}"),
            ("__delitem__", "delitem{when}"),
        ]
        for meth, evt_fmt in pairs:
            register_emit_event(getattr(self, meth), self.emitter, evt_fmt)


class EventMixin:
    events = None
    _models = dict()  # type: ignore

    @classmethod
    def all_models(cls):
        return list(cls._models.values())

    @classmethod
    def identity(cls, data):
        return data.get("id")

    def __new__(cls, data, api):
        # to reuse the same object.
        obj = cls._models.get(cls.identity(data))
        if obj is None:
            obj = super.__new__(cls)
            cls._models[cls.identity(data)] = obj
        return obj

    def __init__(self, data, api):
        super().__init__(ObservableDict(data, __evt=self._emit_data), api)

    def _emit_data(self, event, *args, **kws):
        # helper function for inner data structure.
        return self.events.emit(f"data:{event}", *args, **kws)


def create_models_for(emitter, name_fmt="{emitter_name}{cls_name}"):
    assert issubclass(emitter, EventMixin)

    rv = dict()
    mixin_name = emitter.__name__
    for k, cls in DEFAULT_MODELS.items():
        name = name_fmt.format(cls_name=cls.__name__, emitter_name=mixin_name)
        rv[k] = type(name, (emitter, cls), {})

    return rv


try:
    from pyee import AsyncIOEventEmitter
except ImportError:
    print("pyee is required by AsyncEventMixin.")
else:
    class AsyncEventMixin:
        events = AsyncIOEventEmitter()
