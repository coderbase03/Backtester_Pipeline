import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.telegram_notifier import TelegramNotifier, load_json, build_actionable_table_text


def main():
    p = argparse.ArgumentParser(description='Send batch report to Telegram')
    p.add_argument('--report', default='reports/pipeline_5sub_run_report.json')
    p.add_argument('--total-scan', type=int, default=15)
    args = p.parse_args()

    report_path = Path(args.report)
    report = load_json(report_path)

    notifier = TelegramNotifier.from_secrets()
    if not notifier.is_configured:
        print('TELEGRAM_NOT_CONFIGURED')
        return

    msg = build_actionable_table_text(report, total_scan_target=args.total_scan)
    m = notifier.send_message(msg, parse_mode='HTML')
    print('MSG_OK', m.get('ok'))


if __name__ == '__main__':
    main()
