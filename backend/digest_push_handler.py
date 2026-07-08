from app.digest_push import run_daily_digest_push


def handler(event, context):
    return run_daily_digest_push().to_dict()
