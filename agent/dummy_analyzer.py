from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT = BASE / 'analysis_report_cpp.txt'

if __name__ == '__main__':
    REPORT.write_text('Dummy analysis report')
    print('[+] Dummy analysis written')
