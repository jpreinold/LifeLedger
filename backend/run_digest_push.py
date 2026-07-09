import json

from app.digest_push import run_daily_digest_push


if __name__ == "__main__":
    result = run_daily_digest_push()
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
