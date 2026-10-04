from apscheduler.schedulers.blocking import BlockingScheduler
from .ml.train import train
from .maintenance import maintain


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Singapore")
    scheduler.add_job(
        train, "cron", day_of_week="sun", hour=3, max_instances=1, coalesce=True
    )
    scheduler.add_job(maintain, "cron", hour=4, max_instances=1, coalesce=True)
    scheduler.start()
