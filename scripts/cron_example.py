"""
Example cron wiring (Linux VDS):
# 00:30, 06:30, 12:30, 18:30 partial runs
30 0,6,12,18 * * * /opt/opus/venv/bin/python /opt/opus/scripts/run_random_subreddit_pipeline.py --ideas-target 10 --max-attempts 3 --symbols "BTCUSDT,ETHUSDT,AAPL" --timeframes "1h,4h,1d" --n-bars 300 >> /opt/opus/logs/pipeline.log 2>&1

# 23:40 daily aggregate + telegram
40 23 * * * /opt/opus/venv/bin/python /opt/opus/scripts/daily_report_aggregator.py --send-telegram >> /opt/opus/logs/pipeline.log 2>&1
"""
print(__doc__)
