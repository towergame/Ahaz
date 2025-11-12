import logging

from redis.asyncio import StrictRedis

logger = logging.getLogger(__name__)


class RedisEventManager:
    _redis_client = None

    def __init__(self, redis_url: str):
        self.redis_url = redis_url

    @property
    def redis_client(self) -> StrictRedis:
        if self._redis_client is None:
            self._redis_client = StrictRedis.from_url(self.redis_url)
        return self._redis_client

    async def publish_event(self, channel: str, message: str):
        await self.redis_client.publish(channel, message)

    def subscribe(self):
        return self.redis_client.pubsub()
