import os
import sys
import time
import re
import gzip
import argparse
import configparser
import logging
import statistics as s
from string import Template

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "APP_LOG": None,
    "parser_errors_threshold": 0.1
}

lineformat=re.compile(
    r"""(?P<remote_addr>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) (?P<remote_user>.+)  (?P<http_x_real_ip>.+) \[(?P<time_local>\d{2}\/[a-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} (\+|\-)\d{4})\] ["](?P<method>.+) (?P<url>.+) (?P<proto>.+)["] (?P<status>\d{3}) (?P<body_bytes_sent>\d+) (["](?P<http_referer>(\-)|(.+))["]) (["](?P<http_user_agent>.+)["]) (["](?P<http_x_forwarded_for>(\-)|(.+))["]) (["](?P<http_X_REQUEST_ID>.+)["]) (["](?P<http_X_RB_USER>.+)["]) (?P<request_time>.+)"""
    , re.IGNORECASE)

urls = dict()
parsed_records = 0
total_time = 0

start_time = time.time()

def init_logger(app_log):
    logging.basicConfig(level=logging.INFO, filename=app_log, filemode="w",
                        format="[%(asctime)s] %(levelname).1s %(message)s",
                        datefmt="%Y.%m.%d %H:%M:%S")
    return logging.getLogger(__name__)

def argParser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='./conf.ini', type=str)
    return parser

def get_config(conf_file):
    conf = configparser.ConfigParser()
    try:
        with open(conf_file) as f:
            conf.read_string(f.read())
    except:
        print(f"File {conf_file} does not exist or can't be read")
        sys.exit()
    for line in config:
        try:
            config[line] = conf['LOG_PARSER'][line]
        except:
            pass
    log_dir = config['LOG_DIR']
    report_dir = config['REPORT_DIR']
    report_size = int(config['REPORT_SIZE'])
    app_log = config['APP_LOG']
    return log_dir, report_dir, report_size, app_log

def log_parser(line):
    global parsed_records, total_time, urls
    try:
        line = re.search(lineformat, line.decode('utf-8'))
    except:
        line = re.search(lineformat, line)
    else:
        logger.exception(msg="Can't parse line in log")
    if line:
        datadict = line.groupdict()
        url = datadict["url"]
        request_time = float(datadict["request_time"])
        if url != '' and request_time != '':
            if url in urls:
               urls[url].append(request_time)
            else:
               urls[url] = [request_time]
            parsed_records += 1
            total_time += request_time

def read_log_file(log_dir,log_file):
    if log_file.endswith(".gz"):
            with gzip.open(os.path.join(log_dir, log_file), 'rb') as f:
                data = f.readlines()
    elif log_file.endswith(".log"):
            with open(os.path.join(log_dir, log_file)) as f:
                data = f.readlines()
    else:
        logger.error(f"Incorrect extension in file {log_file}, .gz and .log accepted only, exit")
        sys.exit()
    return data, len(data)

def check_parser_errors(log_records, log_file):
    if log_records == 0:
        logger.error(f"Empty file {log_file}, exit")
        sys.exit()
    try:
        if 1-parsed_records/log_records > config['parser_errors_threshold']:
            logger.error(f"Too many errors incorrect lines in log file {log_file}, exit")
            sys.exit()
    except Exception:
        logger.exception('Fatal Error')
        sys.exit()


def get_stat(urls, report_size):
    stat = []
    for line in urls:
        url_stat = dict()
        url_stat['url'] = line
        url_stat['count'] = len(urls[line])
        url_stat['count_perc'] = round((url_stat['count']/parsed_records)*100,3)
        url_stat['time_sum'] = round(sum(urls[line]),3)
        url_stat['time_perc'] = round((url_stat['time_sum']/total_time)*100,3)
        url_stat['time_avg'] = round(s.mean(urls[line]),3)
        url_stat['time_max'] = round(max(urls[line]),3)
        url_stat['time_med'] = round(s.median(urls[line]),3)
        stat.append(url_stat)
    stat.sort(key=lambda dictionary: dictionary['time_sum'], reverse=True)
    stat = stat[:report_size]
    return stat

def build_report(report_dir,stat,report_date,log_records):
    with open("report.html") as f:
        template = f.read()
    result = Template(template).safe_substitute(table_json = stat)
    with open(os.path.join(report_dir, f'report-{report_date}.html'), "w+") as f:
        f.write(result)
    logger.info(f"New report-{report_date}.html created for {round(time.time() - start_time, 3)} seconds. Parsed records: {parsed_records}, overal log recors: {log_records}.")


def check_report(report_dir,log_date):
    report_date=time.strftime("%Y.%m.%d", time.strptime(str(log_date),"%Y%m%d"))
    for file in os.listdir(report_dir):
        data = re.findall(f"report-{report_date}.html", file)
        if data:
            logger.error(f"There are no new nginx log files to work on, exit")
            sys.exit()
    return(report_date)

def get_log_file(log_dir,report_dir):
    files = dict()
    for file in os.listdir(log_dir):
        basename, extension = os.path.splitext(file)
        log_date = re.findall(r"nginx.+(?P<date>\d{8})", basename)
        if log_date:
            files[file] = int(log_date[0])
    if len(log_date) == 0:
        logger.error(f"There are no nginx logs, exit")
        sys.exit()
    file_date = max(files.values())
    report_date = check_report(report_dir,file_date)
    log = {k: v for k, v in files.items() if v == file_date}
    log_file = list(log.keys())[0]
    logger.info(f"New log file found: {log_file}")
    return report_date, log_file


def main():
    global logger
    # parsing incoming args
    parser = argParser()
    conf_file = vars(parser.parse_args(sys.argv[1:]))
    # generating active config and logger
    if conf_file:
        log_dir, report_dir, report_size, app_log = get_config(conf_file['config'])
    logger = init_logger(app_log)
    # searching log file
    try:
        report_date, log_file = get_log_file(log_dir, report_dir)
    except Exception:
        logger.exception('Fatal Error on getting log file')
        sys.exit()
    # gathering log data tp process
    try:
        log_data, log_records = read_log_file(log_dir,log_file)
        for line in log_data:
            log_parser(line)
    # check total not parsed lines
        check_parser_errors(log_records, log_file)
    except Exception:
        logger.exception('Fatal Error on config file parser')
        sys.exit()
    # calculate stat and build report
    try:
        stat = get_stat(urls, report_size)
        build_report(report_dir, stat, report_date, log_records)
    except Exception:
        logger.exception('Fatal Error on building report')
        sys.exit()


if __name__ == "__main__":
    main()
