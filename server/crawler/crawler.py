import abc
import random
import logging
from typing import Mapping
from dataclasses import is_dataclass, asdict
from .step import Step


_log = logging.getLogger(__name__)

ERROR_DELAYS = [1, 10, 60, 10 * 60, 60 * 60, 24 * 60 * 60]


class Crawler(abc.ABC):
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
    def _find_stage(cls, index):
        if not isinstance(cls.Stage, type):
            raise RuntimeError("task subclass should define a nested Stage class")

        for field in dir(cls.Stage):
            Field = getattr(cls.Stage, field)
            if is_dataclass(Field) and Field.INDEX == index:
                return Field

        raise RuntimeError(
            f"impossible stage index {index} given for {cls.namespace()}"
        )

    @classmethod
    async def step(cls, *, values, state, session):
        # Don't bother stepping unless all the values exist in the required fields
        if not all(values.get(k) for k in cls.fields()):
            return Step(delay=24 * 60 * 60, stage=None)

        if state is None:
            # Initial stage has index 0, and should have every value with a default
            stage = cls._find_stage(0)()
            error = 0
        else:
            stage_index = state.pop("_index")
            error = state.pop("_error", 0)
            stage = cls._find_stage(stage_index)(**state)

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
            # Can only store data (error) when in a state so reuse the stage to retry.
            # This assumes stage hasn't mutated which is up to the various crawlers to
            # ensure in their implementations.
            return Step(delay=delay, stage=stage, error=error,)

        if not isinstance(step, Step):
            raise TypeError(f"step returned invalid data: {step}")

        # Tasks can embed the authors where author paths should belong for convenience.
        # Address that here before saving anything so everything has the right types.
        step.fix_authors()

        return step
