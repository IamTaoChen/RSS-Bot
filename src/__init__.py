
from .Rss import Rss, RssConfig
from .NitterRss import RssNitter
from .Ai import AiAgent


def create_rss(rss_config: RssConfig, ai_agent: AiAgent, translate_to: str = "Chinese") -> Rss | RssNitter:
    """
    Create an instance of Rss or RssNitter based on the type of the RSS feed.
    :param rss_config: The configuration for the RSS feed.
    :param ai_agent: The AI agent to be used for processing the RSS feed.
    :param translate_to: The language to translate the feed to.
    :return: An instance of Rss or RssNitter.
    """
    if rss_config.type.lower() == "nitter":
        return RssNitter(config=rss_config, ai_agent=ai_agent, translate_to=translate_to)
    else:
        return Rss(config=rss_config, ai_agent=ai_agent, translate_to=translate_to)
