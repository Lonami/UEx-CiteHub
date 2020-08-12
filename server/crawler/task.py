import abc
import asyncio
import json
import random
import time
import logging
import datetime
from typing import Mapping
from dataclasses import asdict, is_dataclass
from .step import Step
from ..storage import Storage


DELAY_JITTER_PERCENT = 0.05
_log = logging.getLogger(__name__)

ERROR_DELAYS = [1, 10, 60, 10 * 60, 60 * 60, 24 * 60 * 60]


class StepException(Exception):
    def __init__(self, due):
        super().__init__()
        self.due = due


# TODO tasks are a bit messy because each stores its resume state in its own way
# ideally we'd have a rust-like enum to ensure that only the data we need is saved
# (and we don't have garbage) which maybe we could return to automate the process
#
# similar for set_url which resets due and stage, maybe the tasks should define what
# they require so it can be better generalized and also have a "start state" which
# could be defined through decorators or something
class Task(abc.ABC):
    """
    Tasks are completely stateless, and a class is only used to ensure some
    consistency in the way various tasks are implemented (we could just as
    well have modules with a free-standing function and they would behave like
    a class with class-methods only).
    """

    # Tasks are completely stateless
    Stage = None

    @classmethod
    @abc.abstractmethod
    def namespace(cls) -> str:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def initial_stage(cls):
        # TODO this can probably be stage with index 0 that should have default values set
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def fields(cls) -> Mapping[str, str]:
        # Should return `{field key: field description}`` on required user-provided fields.
        # The description may contain HTML tags.
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def validate_field(self, key, value) -> Mapping:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    async def _step(self, values, stage, session) -> Step:
        # Should be stateless (no internal mutation or mutation of the input stage).
        # This way do our best to achieve atomicy and only if things go well.
        # It can rely on the storage to contain the data from previous successful steps.
        raise NotImplementedError

    @classmethod
    async def step(cls, *, values, state, session):
        if not isinstance(cls.Stage, type):
            raise RuntimeError("task subclass should define a nested Stage class")

        stage_index = state.pop("_index")
        for field in dir(cls.Stage):
            Field = getattr(cls.Stage, field)
            if is_dataclass(Field) and Field.INDEX == stage_index:
                stage = Field(**state)

        # TODO how to handle error in completely-stateless?
        error = 0

        try:
            step = await cls._step(values, stage, session)
        except Exception:
            delay = ERROR_DELAYS[min(error, len(ERROR_DELAYS) - 1)]
            error += 1
            _log.exception(
                "%d consecutive unhandled exception(s) stepping %s, delay for %ds",
                error,
                cls.namespace(),
                delay,
            )

            due = asyncio.get_event_loop().time() + delay
            raise StepException(due)
        else:
            error = 0

        if not isinstance(step, Step):
            raise TypeError(f"step returned invalid data: {step}")

        # Tasks can embed the authors where author paths should belong for convenience.
        # Address that here before saving anything so everything has the right types.
        step.fix_authors()

        # TODO save step.authors, update user_pub_ids, self_publications, citations paths, stage

        jitter_range = step.delay * DELAY_JITTER_PERCENT
        jitter = random.uniform(-jitter_range, jitter_range)
        due = asyncio.get_event_loop().time() + step.delay + jitter
        return step, due
