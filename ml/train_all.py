"""One validated native training command; no model weights are committed."""

from .baselines import train as baselines
from .recommender import train as recommender
from .search import main as search
from .forecast import train as forecast
from .publish_base import publish


def main() -> None:
    for task in [baselines, recommender, search, forecast, publish]:
        task()


if __name__ == "__main__":
    main()
