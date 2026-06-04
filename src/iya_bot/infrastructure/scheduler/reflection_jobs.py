import logging

from iya_bot.application.reflection import ReflectionService

logger = logging.getLogger(__name__)


class ReflectionJobRunner:
    def __init__(self, reflection: ReflectionService, user_limit: int = 20) -> None:
        self._reflection = reflection
        self._user_limit = user_limit
        self._locked = False

    async def reflect_memories(self) -> None:
        if self._locked:
            return

        self._locked = True
        try:
            reflected = await self._reflection.reflect_recent_users(limit=self._user_limit)
            logger.info("Reflected memory for %s users", reflected)
        except Exception:
            logger.exception("Reflection job failed")
        finally:
            self._locked = False
